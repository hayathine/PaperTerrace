

from app.domain.features.correspondence_lang_dict import SUPPORTED_LANGUAGES
from app.providers import get_ai_provider, get_storage_provider
from common.config import settings
from common.dspy_utils.config import setup_dspy
from common.dspy_utils.modules import (
    ContextSummaryModule,
    PaperSummaryModule,
    SectionSummaryModule,
)
from common.dspy_utils.trace import TraceContext, trace_dspy_call
from common.logger import ServiceLogger
from common.dspy_seed_prompt import (
    PAPER_SUMMARY_FROM_PDF_PROMPT,
)
from redis_provider.provider import RedisService

log = ServiceLogger("Summary")

CACHE_TTL_MINUTES = 60


class SummaryError(Exception):
    """要約処理に関する例外"""

    pass


class SummaryService:
    """論文要約サービス"""

    def __init__(self, storage=None):
        self.ai_provider = get_ai_provider()
        self.storage = storage or get_storage_provider()  # Inject storage
        self.redis = RedisService()
        self.model = settings.get("MODEL_SUMMARY", "gemini-2.5-flash-lite")
        self.token_limit = int(settings.get("MAX_INPUT_TOKENS", "900000"))

        # Initialize DSPy
        setup_dspy()
        self.summary_mod = PaperSummaryModule()
        self.section_mod = SectionSummaryModule()
        self.context_mod = ContextSummaryModule()

    async def summarize_full(
        self,
        text: str = "",
        target_lang: str = "ja",
        paper_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
        pdf_bytes: bytes | None = None,
        key_word: str | None = None,
    ) -> tuple[str, str | None]:
        """
        論文全体の包括的な要約を生成する。
        優先的にPDF画像入力方式を使用し、PDF取得失敗時はテキスト方式にフォールバック。
        """
        # Check cache
        paper_info = None
        if paper_id:
            paper_info = self.storage.get_paper(paper_id)
            if paper_info and paper_info.get("full_summary"):
                log.info("summarize_full", "全文要約のキャッシュがヒットしました", paper_id=paper_id)
                return paper_info["full_summary"], None

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        # pdf_bytes未指定の場合、GCSからPDFを取得して画像パスを試みる
        if not pdf_bytes and paper_id:
            try:
                from app.providers import get_image_storage

                info = paper_info or self.storage.get_paper(paper_id)
                if info and info.get("file_hash"):
                    img_storage = get_image_storage()
                    pdf_bytes = img_storage.get_doc_bytes(
                        img_storage.get_doc_path(info["file_hash"])
                    )
                    log.debug(
                        "summarize_full",
                        "画像ベースの要約のためにGCSからPDFバイナリを取得しました",
                        paper_id=paper_id,
                        pdf_size=len(pdf_bytes),
                    )
            except Exception as e:
                log.warning(
                    "summarize_full",
                    "PDFバイナリの取得に失敗しました。テキストベースの要約にフォールバックします",
                    error=str(e),
                    paper_id=paper_id,
                )
                pdf_bytes = None

        try:
            if pdf_bytes:
                # PDF-based summary with context cache
                keyword_focus = ""
                if key_word:
                    keyword_focus = f"[Topic Focus]\nPlease provide more details and context regarding the keyword: '{key_word}' within the summary if applicable."

                prompt = PAPER_SUMMARY_FROM_PDF_PROMPT.format(
                    lang_name=lang_name, keyword_focus=keyword_focus
                )

                # コンテキストキャッシュを取得または作成（chatと共有）
                pdf_cache_name = None
                if paper_id:
                    pdf_cache_key = f"paper_cache_pdf:{paper_id}"
                    pdf_cache_name = self.redis.get(pdf_cache_key)
                    if not pdf_cache_name:
                        try:
                            pdf_cache_name = await self.ai_provider.create_context_cache(
                                model=self.model,
                                contents=pdf_bytes,
                                ttl_minutes=CACHE_TTL_MINUTES,
                            )
                            self.redis.set(
                                pdf_cache_key,
                                pdf_cache_name,
                                expire=CACHE_TTL_MINUTES * 60,
                            )
                            log.info(
                                "summarize_full",
                                "PDFコンテキストキャッシュを作成しました",
                                paper_id=paper_id,
                                cache_name=pdf_cache_name,
                            )
                        except Exception as e:
                            log.warning(
                                "summarize_full",
                                "コンテキストキャッシュの作成に失敗しました。キャッシュなしで続行します",
                                error=str(e),
                                paper_id=paper_id,
                            )
                            pdf_cache_name = None

                log.debug(
                    "summarize_full",
                    "PDFから全文要約を生成中",
                    pdf_size=len(pdf_bytes),
                    cached=pdf_cache_name is not None,
                )
                formatted_text = await self.ai_provider.generate_with_pdf(
                    prompt,
                    pdf_bytes=pdf_bytes if not pdf_cache_name else None,
                    cached_content_name=pdf_cache_name,
                    model=self.model,
                )
            else:
                # Text-based summary logic (Restored)
                safe_text = await self._truncate_to_token_limit(text)
                keyword_focus = ""
                if key_word:
                    keyword_focus = f"Focus on: {key_word}"

                res, trace_id = await trace_dspy_call(
                    "PaperSummaryModule",
                    "PaperSummary",
                    self.summary_mod,
                    {
                        "paper_text": safe_text,
                        "lang_name": lang_name,
                        "user_persona": "Professional Academic Advisor",
                    },
                    context=TraceContext(
                        user_id=user_id, session_id=session_id, paper_id=paper_id
                    ),
                )

                # Format results
                raw_kw = res.key_words
                if isinstance(raw_kw, str):
                    key_words = [k.strip() for k in raw_kw.split(",") if k.strip()]
                elif isinstance(raw_kw, list):
                    key_words = [str(k).strip() for k in raw_kw if k]
                else:
                    key_words = []
                keywords_str = ", ".join(key_words) if key_words else "N/A"

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

            # Save to cache
            if paper_id:
                self.storage.update_paper_full_summary(paper_id, formatted_text)

            return formatted_text, locals().get("trace_id")
        except Exception as e:
            log.exception("summarize_full", "全文要約の生成に失敗しました")
            return f"要約の生成に失敗しました: {str(e)}", None

    async def summarize_sections(
        self,
        text: str,
        target_lang: str = "ja",
        paper_id: str | None = None,
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> list[dict]:
        """セクションごとの要約を生成する"""
        if paper_id:
            paper = self.storage.get_paper(paper_id)
            if paper and paper.get("section_summary_json"):
                import json

                try:
                    return json.loads(paper["section_summary_json"])
                except Exception:
                    pass

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        safe_text = await self._truncate_to_token_limit(text)
        try:
            res, trace_id = await trace_dspy_call(
                "SectionSummaryModule",
                "PaperSummarySections",
                self.section_mod,
                {
                    "paper_text": safe_text,
                    "lang_name": lang_name,
                    "user_persona": "Professional Academic Advisor",
                },
                context=TraceContext(
                    user_id=user_id, session_id=session_id, paper_id=paper_id
                ),
            )
            sections = []
            for item in res.sections:
                if isinstance(item, dict):
                    sections.append(item)
                else:
                    sections.append({"section": "Chapter", "summary": str(item)})

            if paper_id:
                import json

                self.storage.update_paper_section_summary(
                    paper_id, json.dumps(sections, ensure_ascii=False)
                )

            return sections, trace_id
        except Exception as e:
            log.exception("summarize_sections", "セクション要約に失敗しました")
            return [{"section": "Error", "summary": f"要約生成に失敗: {e}"}], "error"

    async def summarize_abstract(self, text: str, target_lang: str = "ja") -> str:
        """抄録を抽出する"""
        import re

        clean_text = re.sub(r"\s+", " ", text[:10000])
        match = re.search(r"(?i)\babstract\b\s*[:\.]?\s*(.*)", clean_text)
        if match:
            abstract_text = match.group(1).strip()
            end_patterns = [
                r"(?i)\bintroduction\b",
                r"(?i)\bindex terms\b",
                r"(?i)\bkeywords\b",
            ]
            earliest_end = 2000
            for pattern in end_patterns:
                end_match = re.search(pattern, abstract_text)
                if end_match and end_match.start() < earliest_end:
                    earliest_end = end_match.start()
            return abstract_text[:earliest_end].strip()
        return "Abstract heading not found."

    async def summarize_context(self, text: str, max_length: int = 500) -> str:
        """AIコンテキスト用の短い要約を生成する（最大max_length文字）。"""
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
                "コンテキスト要約を生成しました",
                summary_length=len(summary),
            )

            return summary[:max_length]
        except Exception as e:
            log.error(
                "summarize_context", "コンテキスト要約の生成に失敗しました", error=str(e)
            )

            return ""

    async def _truncate_to_token_limit(self, text: str) -> str:
        """トークン上限に合わせてテキストを切り詰める（ローカル概算、API呼び出しなし）"""
        if not text:
            return ""
        # 1トークン ≈ 4文字 の概算（Gemini の実測値に近い近似）
        # 5% の安全マージンを取る
        max_chars = int(self.token_limit * 4 * 0.95)
        if len(text) <= max_chars:
            return text
        return text[:max_chars]
