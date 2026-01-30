"""
著者に不利な解釈を与える意見を生成する機能を提供するモジュール
出力例：
    隠れた前提
    未検証条件
    再現性リスク
"""

from src.logger import logger
from src.prompts import (
    ADVERSARIAL_CRITIQUE_PROMPT,
)
from src.providers import get_ai_provider
from src.schemas.adversarial import (
    AdversarialCritiqueResponse as CritiqueResponse,
)


class AdversarialError(Exception):
    """Adversarial review-specific exception."""

    pass


class AdversarialReviewService:
    """Adversarial review service for critical thinking support."""

    def __init__(self):
        self.ai_provider = get_ai_provider()

    async def critique(self, text: str, target_lang: str = "ja") -> dict:
        """
        Analyze the paper from a critical perspective.

        Args:
            text: The paper text
            target_lang: Output language

        Returns:
            Dictionary with critical analysis categories
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        prompt = ADVERSARIAL_CRITIQUE_PROMPT.format(text=text[:12000], lang_name=lang_name)

        try:
            logger.debug(
                "Generating adversarial critique",
                extra={"text_length": len(text)},
            )
            critique = await self.ai_provider.generate(prompt, response_model=CritiqueResponse)

            issue_count = (
                len(critique.hidden_assumptions)
                + len(critique.unverified_conditions)
                + len(critique.reproducibility_risks)
                + len(critique.methodology_concerns)
            )

            logger.info(
                "Adversarial review generated",
                extra={"issue_count": issue_count},
            )
            return critique.model_dump()
        except Exception as e:
            logger.exception(
                "Adversarial review failed",
                extra={"error": str(e)},
            )
            return {
                "error": str(e),
                "hidden_assumptions": [],
                "unverified_conditions": [],
                "reproducibility_risks": [],
                "methodology_concerns": [],
                "overall_assessment": "分析に失敗しました",
            }
