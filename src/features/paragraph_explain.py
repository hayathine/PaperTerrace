"""
パラグラフ単位で詳細な説明を生成する機能を提供するモジュール
"""

import os
from typing import List

from pydantic import BaseModel, Field

from src.logger import logger
from src.providers import get_ai_provider


class ParagraphExplanationResponse(BaseModel):
    """段落の解説結果モデル"""

    main_claim: str = Field(..., description="The core argument or content")
    background_knowledge: str = Field(..., description="Prerequisites or technical terms")
    logic_flow: str = Field(..., description="How the argument or logic is developed")
    key_points: List[str] = Field(..., description="Important implications or notes")


class TermExplanation(BaseModel):
    """専門用語の解説モデル"""

    term: str = Field(..., description="Technical term")
    explanation: str = Field(..., description="Concise explanation")
    importance: str = Field(..., description="high/medium/low")


class TerminologyResponse(BaseModel):
    """用語解説のリストモデル"""

    terms: List[TermExplanation] = Field(..., max_length=10)


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
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        context_hint = ""
        if full_context:
            context_hint = f"""
[Full Paper Context (Excerpt)]
{full_context[:5000]}
"""

        from src.prompts import EXPLAIN_PARAGRAPH_PROMPT

        prompt = EXPLAIN_PARAGRAPH_PROMPT.format(
            context_hint=context_hint, paragraph=paragraph, lang_name=lang_name
        )

        try:
            logger.debug(
                "Generating paragraph explanation",
                extra={"paragraph_length": len(paragraph)},
            )
            analysis: ParagraphExplanationResponse = await self.ai_provider.generate(
                prompt, model=self.model, response_model=ParagraphExplanationResponse
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

    async def explain_terminology(
        self, paragraph: str, terms: list[str] | None = None, lang: str = "ja"
    ) -> list[dict]:
        """
        Extract and explain technical terms in a paragraph.

        Args:
            paragraph: The paragraph to analyze
            terms: Optional list of specific terms to explain
            lang: Target language for explanation

        Returns:
            List of term explanations
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        terms_hint = ""
        if terms:
            terms_hint = f"Specifically explain these terms if found: {', '.join(terms)}"

        from src.prompts import EXPLAIN_TERMINOLOGY_PROMPT

        prompt = EXPLAIN_TERMINOLOGY_PROMPT.format(
            paragraph=paragraph, terms_hint=terms_hint, lang_name=lang_name
        )

        try:
            response: TerminologyResponse = await self.ai_provider.generate(
                prompt, model=self.model, response_model=TerminologyResponse
            )
            logger.info(f"Explained {len(response.terms)} terms")
            return [t.model_dump() for t in response.terms]
        except Exception as e:
            logger.error(f"Terminology explanation failed: {e}")
            return []
