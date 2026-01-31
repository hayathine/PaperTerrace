import os

from src.logger import logger
from src.prompts import (
    CORE_SYSTEM_PROMPT,
    PAPER_SUMMARY_AI_CONTEXT_PROMPT,
    PAPER_SUMMARY_FROM_PDF_PROMPT,
    PAPER_SUMMARY_FULL_PROMPT,
    PAPER_SUMMARY_SECTIONS_PROMPT,
)
from src.providers import get_ai_provider, get_storage_provider
from src.schemas.summary import FullSummaryResponse
from src.schemas.summary import SectionSummaryList as SectionSummariesResponse

from ..translate import SUPPORTED_LANGUAGES


class SummaryError(Exception):
    """要約処理に関する例外"""

    pass


class SummaryService:
    """論文要約サービス"""

    def __init__(self, storage=None):
        self.ai_provider = get_ai_provider()
        self.storage = storage or get_storage_provider()  # Inject storage
        self.model = os.getenv("MODEL_SUMMARY", "gemini-2.0-flash-lite")
        # デフォルト: 90万トークン（Gemini 1.5 Flashは100万上限だがマージン確保）
        self.token_limit = int(os.getenv("MAX_INPUT_TOKENS", "900000"))

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

        logger.warning(f"Token limit exceeded: {count} > {self.token_limit}. Truncating...")

        # 簡易的な反復切り詰め
        current_text = text
        while count > self.token_limit:
            ratio = self.token_limit / count
            # 安全マージン 95%
            cut_len = int(len(current_text) * ratio * 0.95)
            current_text = current_text[:cut_len]
            count = await self.ai_provider.count_tokens(current_text, model=self.model)

        logger.info(f"Truncated to {len(current_text)} chars ({count} tokens)")
        return current_text

    async def summarize_full(
        self,
        text: str = "",
        target_lang: str = "ja",
        paper_id: str | None = None,
        pdf_bytes: bytes | None = None,
    ) -> str:
        """
        論文全体の包括的な要約を生成する。
        pdf_bytesが指定されている場合はPDF直接入力方式を使用。
        paper_idが指定されている場合、キャッシュを確認・保存する。
        """
        # Check cache if paper_id is provided
        if paper_id:
            paper = self.storage.get_paper(paper_id)
            if paper and paper.get("full_summary"):
                logger.info(f"Full summary cache HIT for {paper_id}")
                return paper["full_summary"]

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        try:
            # PDF直接入力方式 (画像ベース)
            if pdf_bytes:
                import io

                import pdfplumber

                logger.debug(
                    "Generating full summary from PDF images",
                    extra={"pdf_size": len(pdf_bytes)},
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

                        logger.info(f"Converted {len(images)} PDF pages to images for summary")
                except Exception as ex:
                    logger.error(f"Failed to convert PDF to images: {ex}")
                    # 失敗した場合はテキストベースにフォールバック... はここでは難しいのでエラー
                    raise SummaryError(f"PDFの解析（画像化）に失敗しました: {ex}")

                prompt = PAPER_SUMMARY_FROM_PDF_PROMPT.format(lang_name=lang_name)
                # 新しく追加した generate_with_images を使用
                raw_response = await self.ai_provider.generate_with_images(
                    prompt, images, model=self.model
                )

                # Parse the response to extract sections
                formatted_text = raw_response.strip()

                logger.info(
                    "Full summary generated from PDF images",
                    extra={"image_count": len(images), "output_length": len(formatted_text)},
                )
            else:
                # 従来のテキストベース方式
                logger.debug(
                    "Generating full summary from text",
                    extra={"text_length": len(text)},
                )
                safe_text = await self._truncate_to_token_limit(text)
                prompt = PAPER_SUMMARY_FULL_PROMPT.format(lang_name=lang_name, paper_text=safe_text)

                analysis: FullSummaryResponse = await self.ai_provider.generate(
                    prompt,
                    model=self.model,
                    response_model=FullSummaryResponse,
                    system_instruction=CORE_SYSTEM_PROMPT,
                )

                # 後方互換性のため整形済みテキストを返す
                result_lines = [
                    f"## Overview\n{analysis.overview}",
                    "\n## Key Contributions",
                    *[f"- {item}" for item in analysis.key_contributions],
                    f"\n## Methodology\n{analysis.methodology}",
                    f"\n## Conclusion\n{analysis.conclusion}",
                ]
                formatted_text = "\n".join(result_lines)

                logger.info(
                    "Full summary generated from text",
                    extra={"input_length": len(text), "output_length": len(formatted_text)},
                )

            # Save to cache
            if paper_id:
                self.storage.update_paper_full_summary(paper_id, formatted_text)
                logger.info(f"Full summary cached for {paper_id}")

            return formatted_text
        except Exception as e:
            logger.exception(
                "Full summary generation failed",
                extra={"error": str(e), "text_length": len(text) if text else 0},
            )
            return f"要約の生成に失敗しました: {str(e)}"

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
                    logger.info(f"Section summary cache HIT for {paper_id}")
                    return cached_sections
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON in section summary cache for {paper_id}")

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        safe_text = await self._truncate_to_token_limit(text)
        prompt = PAPER_SUMMARY_SECTIONS_PROMPT.format(lang_name=lang_name, paper_text=safe_text)

        try:
            logger.debug(
                "Generating section summary",
                extra={"text_length": len(text)},
            )
            response: SectionSummariesResponse = await self.ai_provider.generate(
                prompt,
                model=self.model,
                response_model=SectionSummariesResponse,
                system_instruction=CORE_SYSTEM_PROMPT,
            )

            logger.info(
                "Section summary generated",
                extra={"section_count": len(response.sections)},
            )
            sections = [s.model_dump() for s in response.sections]

            # Save to cache
            if paper_id:
                import json

                self.storage.update_paper_section_summary(
                    paper_id, json.dumps(sections, ensure_ascii=False)
                )
                logger.info(f"Section summary cached for {paper_id}")

            return sections
        except Exception as e:
            logger.exception(
                "Section summary failed",
                extra={"error": str(e)},
            )
            return [{"section": "Error", "summary": f"要約生成に失敗: {e}"}]

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

        logger.info("Extracting abstract from text (substituting AI generation)")

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
            # コンテキスト生成には冒頭部分のみ使用
            prompt = PAPER_SUMMARY_AI_CONTEXT_PROMPT.format(
                max_length=max_length, paper_text=text[:20000]
            )
            summary = await self.ai_provider.generate(
                prompt, model=self.model, system_instruction=CORE_SYSTEM_PROMPT
            )
            logger.info(f"Context summary generated (length: {len(summary)})")
            return summary[:max_length]
        except Exception as e:
            logger.error(f"Context summary generation failed: {e}")
            return ""
