import os

from app.domain.features.correspondence_lang_dict import SUPPORTED_LANGUAGES
from app.providers import get_ai_provider, get_storage_provider
from common.dspy.config import setup_dspy
from common.dspy.modules import (
    ContextSummaryModule,
    PaperSummaryModule,
    SectionSummaryModule,
)
from common.dspy.trace import TraceContext, trace_dspy_call
from common.logger import ServiceLogger
from common.prompts import (
    PAPER_SUMMARY_FROM_PDF_PROMPT,
    PAPER_SUMMARY_FULL_PROMPT,
)

log = ServiceLogger("Summary")


class SummaryError(Exception):
    """要約処理に関する例外"""

    pass


class SummaryService:
    """論文要約サービス"""

    def __init__(self, storage=None):
        self.ai_provider = get_ai_provider()
        self.storage = storage or get_storage_provider()  # Inject storage
        self.model = os.getenv("MODEL_SUMMARY", "gemini-2.5-flash-lite")
        # デフォルト: 90万トークン（Gemini 1.5 Flashは100万上限だがマージン確保）
        self.token_limit = int(os.getenv("MAX_INPUT_TOKENS", "900000"))

        # Initialize DSPy
        setup_dspy()
        self.summary_mod = PaperSummaryModule()
        self.section_mod = SectionSummaryModule()
        self.context_mod = ContextSummaryModule()

    async def _truncate_to_token_limit(self, text: str) -> str:
        """
        トークン数を確認し、制限を超える場合は切り詰める。
        API呼び出し節約のため、文字数ベースのヒューリスティック判定を併用。
        """
        # 文字数が制限値より大幅に少ない場合はスキップ
        if len(text) < self.token_limit:
            return text

        count = await self.ai_provider.count_tokens(text, model=self.model)
        if count <= self.token_limit:
            return text

        log.warning(
            "truncate",
            "Token limit exceeded. Truncating...",
            count=count,
            limit=self.token_limit,
        )

        # 二分探索で適切な切り詰め長さを効率的に探索 (最大 5 回の API コールで収束)
        # 初期推定値: トークン比率 × 安全マージン 90%
        lo = 0
        hi = int(len(text) * self.token_limit / count * 0.90)
        best_text = text[:hi]

        for _ in range(5):
            if hi - lo < 100:
                break
            mid = (lo + hi) // 2
            candidate = text[:mid]
            mid_count = await self.ai_provider.count_tokens(candidate, model=self.model)
            if mid_count <= self.token_limit:
                best_text = candidate
                lo = mid
            else:
                hi = mid

        log.info(
            "truncate",
            "Truncated text",
            char_count=len(best_text),
        )

        return best_text

    async def summarize_full(
        self,
        text: str = "",
        target_lang: str = "ja",
        paper_id: str | None = None,
        pdf_bytes: bytes | None = None,
        key_word: str | None = None,
    ) -> tuple[str, str | None]:
        """
        論文全体の包括的な要約を生成する。
        pdf_bytesが指定されている場合はPDF直接入力方式を使用。
        paper_idが指定されている場合、キャッシュを確認・保存する。
        """
        # Check cache if paper_id is provided
        if paper_id:
            paper = self.storage.get_paper(paper_id)
            if paper and paper.get("full_summary"):
                log.info("summarize_full", "Full summary cache HIT", paper_id=paper_id)
                return paper["full_summary"], None

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        try:
            # PDF直接入力方式 (画像ベース)
            if pdf_bytes:
                import io

                import pdfplumber

                log.debug(
                    "summarize_full",
                    "Generating full summary from PDF images",
                    pdf_size=len(pdf_bytes),
                )

                images = []
                try:
                    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                        # 全ページか、多い場合は制限するか検討。とりあえず全ページ試行。
                        # ただし、極端に多い場合は件数を絞る（例: 最初の20ページ）
                        max_pages = 25
                        pages_to_process = pdf.pages[:max_pages]

                        for i, page in enumerate(pages_to_process):
                            # 解像度を抑えてトークンと処理時間を節約 (100 DPI)
                            page_img = page.to_image(resolution=100)
                            buf = io.BytesIO()
                            page_img.original.save(buf, format="PNG")
                            images.append(buf.getvalue())

                        log.info(
                            "summarize_full",
                            "Converted PDF pages to images for summary",
                            page_count=len(images),
                        )

                except Exception as ex:
                    log.error(
                        "summarize_full",
                        "Failed to convert PDF to images",
                        error=str(ex),
                    )

                    # 失敗した場合はテキストベースにフォールバック... はここでは難しいのでエラー

                    raise SummaryError(f"PDFの解析（画像化）に失敗しました: {ex}")

                keyword_focus = ""
                if key_word:
                    keyword_focus = f"[Topic Focus]\nPlease provide more details and context regarding the keyword: '{key_word}' within the summary if applicable."

                prompt = PAPER_SUMMARY_FROM_PDF_PROMPT.format(
                    lang_name=lang_name, keyword_focus=keyword_focus
                )
                # 新しく追加した generate_with_images を使用
                raw_response = await self.ai_provider.generate_with_images(
                    prompt, images, model=self.model
                )

                # Parse the response to extract sections
                formatted_text = raw_response.strip()

                log.info(
                    "summarize_full",
                    "Full summary generated from PDF images",
                    image_count=len(images),
                    output_length=len(formatted_text),
                )
            else:
                # 従来のテキストベース方式
                log.debug(
                    "summarize_full",
                    "Generating full summary from text",
                    text_length=len(text),
                )

                safe_text = await self._truncate_to_token_limit(text)

                keyword_focus = ""
                if key_word:
                    keyword_focus = f"[Topic Focus]\nPlease provide more details and context regarding the keyword: '{key_word}' within the summary if applicable."

                prompt = PAPER_SUMMARY_FULL_PROMPT.format(
                    lang_name=lang_name,
                    paper_text=safe_text,
                    keyword_focus=keyword_focus,
                )

                # DSPy version
                res, trace_id = await trace_dspy_call(
                    "PaperSummaryModule",
                    "PaperSummary",
                    self.summary_mod,
                    {"paper_text": safe_text, "lang_name": lang_name},
                    context=TraceContext(paper_id=paper_id),
                )

                # DSPy may return key_words as None, [], or a raw string when
                # list parsing fails. Normalize to a proper list before joining.
                raw_kw = res.key_words
                if isinstance(raw_kw, str):
                    key_words = [k.strip() for k in raw_kw.split(",") if k.strip()]
                elif isinstance(raw_kw, list):
                    key_words = [str(k).strip() for k in raw_kw if k]
                else:
                    key_words = []
                keywords_str = ", ".join(key_words) if key_words else "N/A"

                # Check if target is English, otherwise default to Japanese headers
                if target_lang == "en":
                    result_lines = [
                        f"## Overview\n{res.overview}",
                        "\n## Key Contributions",
                        *[f"- {item}" for item in res.key_contributions],
                        f"\n## Methodology\n{res.methodology}",
                        f"\n## Conclusion\n{res.conclusion}",
                        "\n## Key Words",
                        keywords_str,
                    ]
                else:
                    result_lines = [
                        f"## 概要\n{res.overview}",
                        "\n## 主な貢献",
                        *[f"- {item}" for item in res.key_contributions],
                        f"\n## 手法\n{res.methodology}",
                        f"\n## 結論\n{res.conclusion}",
                        "\n## キーワード",
                        keywords_str,
                    ]
                formatted_text = "\n".join(result_lines)

                log.info(
                    "summarize_full",
                    "Full summary generated from text",
                    input_length=len(text),
                    output_length=len(formatted_text),
                )

            # Save to cache
            if paper_id:
                self.storage.update_paper_full_summary(paper_id, formatted_text)
                log.info("summarize_full", "Full summary cached", paper_id=paper_id)

            return formatted_text, locals().get("trace_id")
        except Exception as e:
            log.exception(
                "summarize_full",
                "Full summary generation failed",
                text_length=len(text) if text else 0,
            )
            return f"要約の生成に失敗しました: {str(e)}", None

    async def summarize_sections(
        self, text: str, target_lang: str = "ja", paper_id: str | None = None
    ) -> list[dict]:
        """
        セクションごとの要約を生成する。
        paper_idが指定されている場合、キャッシュを確認・保存する。
        """
        # Check cache
        if paper_id:
            paper = self.storage.get_paper(paper_id)
            if paper and paper.get("section_summary_json"):
                import json

                try:
                    cached_sections = json.loads(paper["section_summary_json"])
                    log.info(
                        "summarize_sections",
                        "Section summary cache HIT",
                        paper_id=paper_id,
                    )

                    return cached_sections
                except json.JSONDecodeError:
                    log.warning(
                        "summarize_sections",
                        "Invalid JSON in section summary cache",
                        paper_id=paper_id,
                    )

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        safe_text = await self._truncate_to_token_limit(text)
        try:
            log.debug(
                "summarize_sections",
                "Generating section summary",
                text_length=len(text),
            )
            # DSPy version

            res, trace_id = await trace_dspy_call(
                "SectionSummaryModule",
                "PaperSummarySections",
                self.section_mod,
                {"paper_text": safe_text, "lang_name": lang_name},
                context=TraceContext(paper_id=paper_id),
            )

            sections = []
            for item in res.sections:
                if isinstance(item, dict):
                    sections.append(item)
                else:
                    # In case DSPy returns a string or something else
                    sections.append({"section": "Chapter", "summary": str(item)})

            log.info(
                "summarize_sections",
                "Section summary generated",
                section_count=len(sections),
            )

            # Save to cache
            if paper_id:
                import json

                self.storage.update_paper_section_summary(
                    paper_id, json.dumps(sections, ensure_ascii=False)
                )
                log.info(
                    "summarize_sections", "Section summary cached", paper_id=paper_id
                )

            return sections, trace_id
        except Exception as e:
            log.exception(
                "summarize_sections",
                "Section summary failed",
            )
            return [{"section": "Error", "summary": f"要約生成に失敗: {e}"}], "error"

    async def summarize_abstract(self, text: str, target_lang: str = "ja") -> str:
        """
        Extract the actual abstract from the text instead of generating it with AI.
        (Substitutes PAPER_SUMMARY_ABSTRACT_PROMPT as requested)

        Args:
            text: Paper text
            target_lang: Output language (ignored here as we extract verbatim)

        Returns:
            Extracted abstract text
        """
        import re

        log.info(
            "summarize_abstract",
            "Extracting abstract from text (substituting AI generation)",
        )

        # Normalization: clean up excessive whitespace/newlines

        clean_text = re.sub(r"\s+", " ", text[:10000])

        # Search for "Abstract" (case-insensitive)
        match = re.search(r"(?i)\babstract\b\s*[:\.]?\s*(.*)", clean_text)

        if match:
            abstract_text = match.group(1).strip()
            # Stop at common next section headings
            end_patterns = [
                r"(?i)\bintroduction\b",
                r"(?i)\bindex terms\b",
                r"(?i)\bkeywords\b",
                r"(?i)\bcontents\b",
            ]

            earliest_end = 2000  # Default limit
            for pattern in end_patterns:
                end_match = re.search(pattern, abstract_text)
                if end_match and end_match.start() < earliest_end:
                    earliest_end = end_match.start()

            return abstract_text[:earliest_end].strip()

        return "Abstract heading not found in text."

    async def summarize_context(self, text: str, max_length: int = 500) -> str:
        """
        AIコンテキスト用の短い要約を生成する（最大max_length文字）。
        """
        try:
            # DSPy version
            res, trace_id = await trace_dspy_call(
                "ContextSummaryModule",
                "PaperSummaryContext",
                self.context_mod,
                {"paper_text": text[:20000], "max_length": max_length},
            )
            summary = res.summary
            log.info(
                "summarize_context",
                "Context summary generated",
                summary_length=len(summary),
            )

            return summary[:max_length]
        except Exception as e:
            log.error(
                "summarize_context", "Context summary generation failed", error=str(e)
            )

            return ""
