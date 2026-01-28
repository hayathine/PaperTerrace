"""
スマート要約機能を提供するモジュール
論文全体、セクション別、アブストラクト形式の要約を生成
"""

import json
import os

from src.logger import logger
from src.providers import get_ai_provider


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

        prompt = f"""Summarize the following paper in {lang_name}.

[Paper Text]
{text[:15000]}

Format the summary as follows in {lang_name}:

## Overview
(1-2 sentences summarizing the main theme)

## Key Contributions
(3-5 bullet points)

## Methodology
(Concise explanation of methods used)

## Conclusion
(Key findings and implications)
"""

        try:
            logger.debug(
                "Generating full summary",
                extra={"text_length": len(text)},
            )
            summary = await self.ai_provider.generate(prompt, model=self.model)
            summary = summary.strip()

            if not summary:
                logger.warning("Empty summary result")
                raise SummaryError("Empty summary result")

            logger.info(
                "Full summary generated",
                extra={"input_length": len(text), "output_length": len(summary)},
            )
            return summary
        except SummaryError:
            raise
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

        prompt = f"""Summarize the following paper section by section in {lang_name}.

[Paper Text]
{text[:15000]}

For each section, output the result in the following JSON format:
[
  {{"section": "Section Title", "summary": "Summary (2-3 sentences) in {lang_name}"}},
  ...
]

Output ONLY valid JSON.
"""

        try:
            logger.debug(
                "Generating section summary",
                extra={"text_length": len(text)},
            )
            response = await self.ai_provider.generate(prompt, model=self.model)
            # Parse JSON response
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            sections = json.loads(response)

            if not sections:
                logger.warning("Empty section summary result")
                raise SummaryError("No sections found")

            logger.info(
                "Section summary generated",
                extra={"section_count": len(sections)},
            )
            return sections
        except json.JSONDecodeError as e:
            logger.exception(
                "Failed to parse section summary JSON",
                extra={"error": str(e)},
            )
            return [{"section": "Error", "summary": "セクション要約の解析に失敗しました"}]
        except SummaryError:
            raise
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

        prompt = f"""Create an abstract of the following paper in {lang_name}.
(Length: approx. 100-200 words or equivalent characters)

{text[:10000]}

Write in a concise, academic style in {lang_name}.
"""

        try:
            abstract = await self.ai_provider.generate(prompt, model=self.model)
            logger.info("Abstract summary generated")
            return abstract
        except Exception as e:
            logger.error(f"Abstract generation failed: {e}")
            return f"要旨の生成に失敗しました: {str(e)}"
