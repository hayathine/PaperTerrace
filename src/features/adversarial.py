"""
著者に不利な解釈を与える意見を生成する機能を提供するモジュール
出力例：
    隠れた前提
    未検証条件
    再現性リスク
"""

from typing import List

from pydantic import BaseModel, Field

from src.logger import logger
from src.providers import get_ai_provider


class HiddenAssumption(BaseModel):
    assumption: str
    risk: str
    severity: str


class UnverifiedCondition(BaseModel):
    condition: str
    impact: str
    severity: str


class ReproducibilityRisk(BaseModel):
    risk: str
    detail: str
    severity: str


class MethodologyConcern(BaseModel):
    concern: str
    suggestion: str
    severity: str


class CritiqueResponse(BaseModel):
    hidden_assumptions: List[HiddenAssumption]
    unverified_conditions: List[UnverifiedCondition]
    reproducibility_risks: List[ReproducibilityRisk]
    methodology_concerns: List[MethodologyConcern]
    overall_assessment: str


class Limitation(BaseModel):
    limitation: str
    evidence: str
    impact: str
    severity: str


class LimitationsResponse(BaseModel):
    limitations: List[Limitation]


class CounterArgumentsResponse(BaseModel):
    counterarguments: List[str] = Field(..., description="3 potential counterarguments")


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

        prompt = f"""You are a rigorous reviewer. Analyze the following paper from a critical perspective and identify potential issues.

[Paper Text]
{text[:12000]}

Please output in the following JSON format in {lang_name}:
{{
  "hidden_assumptions": [
    {{"assumption": "Hidden assumption", "risk": "Why it is a problem", "severity": "high/medium/low"}}
  ],
  "unverified_conditions": [
    {{"condition": "Unverified condition", "impact": "Impact if not verified", "severity": "high/medium/low"}}
  ],
  "reproducibility_risks": [
    {{"risk": "Reproducibility risk", "detail": "Detailed explanation", "severity": "high/medium/low"}}
  ],
  "methodology_concerns": [
    {{"concern": "Methodological concern", "suggestion": "Suggestion for improvement", "severity": "high/medium/low"}}
  ],
  "overall_assessment": "Overall assessment (2-3 sentences)"
}}

Be constructive but critical. Output ONLY valid JSON.
"""

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

        prompt = f"""Identify limitations in the following paper that may not be explicitly stated by the authors.

[Paper Text]
{text[:10000]}

Output in the following JSON format in {lang_name}:
[
  {{
    "limitation": "Explanation of limitation",
    "evidence": "Basis for this judgment",
    "impact": "Impact on research results",
    "severity": "high/medium/low"
  }}
]

Max 5 items. Output ONLY valid JSON.
"""

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

        prompt = f"""Generate 3 potential counterarguments to the following claim in {lang_name}.
{context_hint}

[Claim]
{claim}

Provide constructive and academic counterarguments, 2-3 sentences each.
Output as a numbered list.
"""

        try:
            response: CounterArgumentsResponse = await self.ai_provider.generate(
                prompt, response_model=CounterArgumentsResponse
            )
            logger.info(f"Generated {len(response.counterarguments)} counterarguments")
            return response.counterarguments
        except Exception as e:
            logger.error(f"Counterargument generation failed: {e}")
            return []
