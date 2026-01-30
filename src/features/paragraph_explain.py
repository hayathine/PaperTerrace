"""
パラグラフ単位で詳細な説明を生成する機能を提供するモジュール
"""

import os

from src.logger import logger
from src.prompts import (
    CORE_SYSTEM_PROMPT,
    PARAGRAPH_EXPLAIN_PROMPT,
    PARAGRAPH_TRANSLATE_PROMPT,
)
from src.providers import get_ai_provider
from src.schemas.paragraph_analysis import (
    ParagraphExplanationResponse,
)

from .translate import SUPPORTED_LANGUAGES


class ParagraphExplainError(Exception):
    """Paragraph explanation-specific exception."""

    pass


class ParagraphExplainService:
    """Paragraph explanation service for deep understanding."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = os.getenv("MODEL_PARAGRAPH", "gemini-2.0-flash")

    async def explain(self, paragraph: str, full_context: str = "", lang: str = "ja") -> str:
        """
        Generate a detailed explanation of a paragraph.

        Args:
            paragraph: The paragraph to explain
            full_context: The full paper text for context
            lang: Target language for the explanation

        Returns:
            Detailed explanation in the target language
        """
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        context_hint = ""
        if full_context:
            context_hint = f"""
[Full Paper Context (Excerpt)]
{full_context[:5000]}
"""

        prompt = PARAGRAPH_EXPLAIN_PROMPT.format(
            context_hint=context_hint, paragraph=paragraph, lang_name=lang_name
        )

        try:
            logger.debug(
                "Generating paragraph explanation",
                extra={"paragraph_length": len(paragraph)},
            )
            analysis: ParagraphExplanationResponse = await self.ai_provider.generate(
                prompt,
                model=self.model,
                response_model=ParagraphExplanationResponse,
                system_instruction=CORE_SYSTEM_PROMPT,
            )

            # 整形された文字列として返す（後方互換性のため）
            result_lines = [
                f"### Main Claim\n{analysis.main_claim}",
                f"\n### Background Knowledge\n{analysis.background_knowledge}",
                f"\n### Logic Flow\n{analysis.logic_flow}",
                "\n### Key Points",
                *[f"- {item}" for item in analysis.key_points],
            ]
            formatted_text = "\n".join(result_lines)

            logger.info(
                "Paragraph explanation generated",
                extra={"input_length": len(paragraph), "output_length": len(formatted_text)},
            )
            return formatted_text
        except Exception as e:
            logger.exception(
                "Paragraph explanation failed",
                extra={"error": str(e)},
            )
            return f"解説の生成に失敗しました: {e}"

    async def translate_paragraph(
        self, paragraph: str, full_context: str = "", lang: str = "ja"
    ) -> str:
        """
        Translate the paragraph directly.

        Args:
            paragraph: The paragraph to translate
            full_context: Context for better translation accuracy
            lang: Target language

        Returns:
            Translated text
        """
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        context_hint = ""
        if full_context:
            context_hint = f"\n[Full Paper Context (Excerpt)]\n{full_context[:5000]}\n"

        prompt = PARAGRAPH_TRANSLATE_PROMPT.format(
            context_hint=context_hint, paragraph=paragraph, lang_name=lang_name
        )

        try:
            logger.debug(
                "Translating paragraph",
                extra={"paragraph_length": len(paragraph)},
            )
            translation = await self.ai_provider.generate(
                prompt,
                model=self.model,
                system_instruction=CORE_SYSTEM_PROMPT,
            )
            return translation.strip()
        except Exception as e:
            logger.exception(
                "Paragraph translation failed",
                extra={"error": str(e)},
            )
            return f"翻訳に失敗しました: {e}"
