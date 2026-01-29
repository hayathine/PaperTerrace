"""
著者に不利な解釈を与える意見を生成する機能を提供するモジュール
出力例：
    隠れた前提
    未検証条件
    再現性リスク
"""

from src.logger import logger
from src.prompts import (
    ADVERSARIAL_COUNTERARGUMENTS_PROMPT,
    ADVERSARIAL_CRITIQUE_PROMPT,
    ADVERSARIAL_LIMITATIONS_PROMPT,
)
from src.providers import get_ai_provider
from src.schemas.adversarial import (
    AdversarialCritiqueResponse as CritiqueResponse,
)
from src.schemas.adversarial import (
    CounterArgumentsResponse,
)
from src.schemas.adversarial import (
    LimitationList as LimitationsResponse,
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
            # 既存のコードが辞書を期待している可能性があるため、dictに変換して返す（またはフロントエンドまで修正する）
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

    async def identify_limitations(self, text: str, target_lang: str = "ja") -> list[dict]:
        """
        Identify limitations not explicitly stated by authors.

        Args:
            text: The paper text
            target_lang: Output language

        Returns:
            List of identified limitations
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        prompt = ADVERSARIAL_LIMITATIONS_PROMPT.format(text=text[:10000], lang_name=lang_name)

        try:
            logger.debug(
                "Identifying limitations",
                extra={"text_length": len(text)},
            )
            response = await self.ai_provider.generate(prompt, response_model=LimitationsResponse)

            logger.info(
                "Limitations identified",
                extra={"limitation_count": len(response.limitations)},
            )
            return [lim.model_dump() for lim in response.limitations]
        except Exception as e:
            logger.exception(
                "Limitation identification failed",
                extra={"error": str(e)},
            )
            return []

    async def suggest_counterarguments(
        self, claim: str, context: str = "", target_lang: str = "ja"
    ) -> list[str]:
        """
        Generate potential counterarguments to a specific claim.

        Args:
            claim: The claim to counter
            context: Additional context
            target_lang: Output language

        Returns:
            List of counterarguments
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        context_hint = f"\n[Context]\n{context[:3000]}" if context else ""

        prompt = ADVERSARIAL_COUNTERARGUMENTS_PROMPT.format(
            lang_name=lang_name, context_hint=context_hint, claim=claim
        )

        try:
            response: CounterArgumentsResponse = await self.ai_provider.generate(
                prompt, response_model=CounterArgumentsResponse
            )
            logger.info(f"Generated {len(response.counterarguments)} counterarguments")
            return response.counterarguments
        except Exception as e:
            logger.error(f"Counterargument generation failed: {e}")
            return []
