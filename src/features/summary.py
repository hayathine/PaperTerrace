import os
from typing import List

from pydantic import BaseModel, Field

from src.logger import logger
from src.providers import get_ai_provider


class FullSummaryResponse(BaseModel):
    """論文全体の要約結果モデル"""

    overview: str = Field(..., description="1-2 sentences summarizing the main theme")
    key_contributions: List[str] = Field(..., description="3-5 bullet points of contributions")
    methodology: str = Field(..., description="Concise explanation of methods used")
    conclusion: str = Field(..., description="Key findings and implications")


class SectionSummary(BaseModel):
    """セクション別の要約モデル"""

    section: str = Field(..., description="Section title")
    summary: str = Field(..., description="2-3 sentences summary")


class SectionSummariesResponse(BaseModel):
    """セクション別要約のリストモデル"""

    sections: List[SectionSummary]


class SummaryError(Exception):
    """Summary-specific exception."""

    pass


class SummaryService:
    """Summary generation service for papers."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = os.getenv("MODEL_SUMMARY", "gemini-2.0-flash")

    async def summarize_full(self, text: str, target_lang: str = "ja") -> str:
        """
        Generate a comprehensive summary of the entire paper.

        Args:
            text: The full paper text
            target_lang: The language to summarize in

        Returns:
            A structured summary in the target language
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        from src.prompts import SUMMARY_FULL_PROMPT

        prompt = SUMMARY_FULL_PROMPT.format(lang_name=lang_name, paper_text=text[:15000])

        try:
            logger.debug(
                "Generating full summary",
                extra={"text_length": len(text)},
            )
            analysis: FullSummaryResponse = await self.ai_provider.generate(
                prompt, model=self.model, response_model=FullSummaryResponse
            )

            # 整形された文字列として返す（後方互換性のため）
            result_lines = [
                f"## Overview\n{analysis.overview}",
                "\n## Key Contributions",
                *[f"- {item}" for item in analysis.key_contributions],
                f"\n## Methodology\n{analysis.methodology}",
                f"\n## Conclusion\n{analysis.conclusion}",
            ]
            formatted_text = "\n".join(result_lines)

            logger.info(
                "Full summary generated",
                extra={"input_length": len(text), "output_length": len(formatted_text)},
            )
            return formatted_text
        except Exception as e:
            logger.exception(
                "Full summary generation failed",
                extra={"error": str(e), "text_length": len(text)},
            )
            return f"要約の生成に失敗しました: {str(e)}"

    async def summarize_sections(self, text: str, target_lang: str = "ja") -> list[dict]:
        """
        Generate section-by-section summaries.

        Args:
            text: The full paper text
            target_lang: The language to summarize in

        Returns:
            List of section summaries with title and content
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        from src.prompts import SUMMARY_SECTIONS_PROMPT

        prompt = SUMMARY_SECTIONS_PROMPT.format(lang_name=lang_name, paper_text=text[:15000])

        try:
            logger.debug(
                "Generating section summary",
                extra={"text_length": len(text)},
            )
            response: SectionSummariesResponse = await self.ai_provider.generate(
                prompt, model=self.model, response_model=SectionSummariesResponse
            )

            logger.info(
                "Section summary generated",
                extra={"section_count": len(response.sections)},
            )
            return [s.model_dump() for s in response.sections]
        except Exception as e:
            logger.exception(
                "Section summary failed",
                extra={"error": str(e)},
            )
            return [{"section": "Error", "summary": f"要約生成に失敗: {e}"}]

    async def summarize_abstract(self, text: str, target_lang: str = "ja") -> str:
        """
        Generate a one-paragraph abstract-style summary.

        Args:
            text: The paper text
            target_lang: The language to summarize in

        Returns:
            A concise abstract in the target language
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        from src.prompts import SUMMARY_ABSTRACT_PROMPT

        prompt = SUMMARY_ABSTRACT_PROMPT.format(lang_name=lang_name, paper_text=text[:10000])

        try:
            abstract = await self.ai_provider.generate(prompt, model=self.model)
            logger.info("Abstract summary generated")
            return abstract
        except Exception as e:
            logger.error(f"Abstract generation failed: {e}")
            return f"要旨の生成に失敗しました: {str(e)}"

    async def summarize_context(self, text: str, max_length: int = 500) -> str:
        """
        Generate a short summary for AI context (max 500 chars).
        """
        try:
            # Use a fast model for context summarization if possible
            from src.prompts import SUMMARY_CONTEXT_PROMPT

            prompt = SUMMARY_CONTEXT_PROMPT.format(max_length=max_length, paper_text=text[:10000])
            summary = await self.ai_provider.generate(prompt, model=self.model)
            logger.info(f"Context summary generated (length: {len(summary)})")
            return summary[:max_length]
        except Exception as e:
            logger.error(f"Context summary generation failed: {e}")
            return ""
