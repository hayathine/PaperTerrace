"""
著者に不利な解釈を与える意見を生成する機能を提供するモジュール
出力例：
    隠れた前提
    未検証条件
    再現性リスク
"""

import json

from src.logger import logger
from src.providers import get_ai_provider


class AdversarialError(Exception):
    """Adversarial review-specific exception."""

    pass


class AdversarialReviewService:
    """Adversarial review service for critical thinking support."""

    def __init__(self):
        self.ai_provider = get_ai_provider()

    async def critique(self, text: str) -> dict:
        """
        Analyze the paper from a critical perspective.

        Args:
            text: The paper text

        Returns:
            Dictionary with critical analysis categories
        """
        prompt = f"""あなたは厳格なレビュアーです。以下の論文を批判的な視点から分析し、
潜在的な問題点を指摘してください。

【論文テキスト】
{text[:12000]}

以下のJSON形式で出力してください：
{{
  "hidden_assumptions": [
    {{"assumption": "隠れた前提", "risk": "それが問題となる理由", "severity": "high/medium/low"}}
  ],
  "unverified_conditions": [
    {{"condition": "未検証の条件", "impact": "検証されていない場合の影響", "severity": "high/medium/low"}}
  ],
  "reproducibility_risks": [
    {{"risk": "再現性のリスク", "detail": "詳細な説明", "severity": "high/medium/low"}}
  ],
  "methodology_concerns": [
    {{"concern": "方法論上の懸念", "suggestion": "改善提案", "severity": "high/medium/low"}}
  ],
  "overall_assessment": "全体的な評価（2-3文）"
}}

建設的な批判を心がけてください。JSONのみを出力してください。"""

        try:
            logger.debug(
                "Generating adversarial critique",
                extra={"text_length": len(text)},
            )
            response = await self.ai_provider.generate(prompt)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            critique = json.loads(response)

            issue_count = (
                len(critique.get("hidden_assumptions", []))
                + len(critique.get("unverified_conditions", []))
                + len(critique.get("reproducibility_risks", []))
                + len(critique.get("methodology_concerns", []))
            )

            logger.info(
                "Adversarial review generated",
                extra={"issue_count": issue_count},
            )
            return critique
        except json.JSONDecodeError as e:
            logger.exception(
                "Failed to parse critique JSON",
                extra={"error": str(e)},
            )
            return {
                "error": "JSON解析エラー",
                "hidden_assumptions": [],
                "unverified_conditions": [],
                "reproducibility_risks": [],
                "methodology_concerns": [],
                "overall_assessment": "分析結果の解析に失敗しました",
            }
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

    async def identify_limitations(self, text: str) -> list[dict]:
        """
        Identify limitations not explicitly stated by authors.

        Args:
            text: The paper text

        Returns:
            List of identified limitations
        """
        prompt = f"""以下の論文から、著者が明示的に述べていない可能性のある限界を特定してください。

【論文テキスト】
{text[:10000]}

以下のJSON形式で出力してください：
[
  {{
    "limitation": "限界の説明",
    "evidence": "そう判断した根拠",
    "impact": "研究結果への影響",
    "severity": "high/medium/low"
  }}
]

最大5件まで。JSONのみを出力してください。"""

        try:
            logger.debug(
                "Identifying limitations",
                extra={"text_length": len(text)},
            )
            response = await self.ai_provider.generate(prompt)
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]

            limitations = json.loads(response)

            logger.info(
                "Limitations identified",
                extra={"limitation_count": len(limitations)},
            )
            return limitations
        except json.JSONDecodeError as e:
            logger.exception(
                "Failed to parse limitations JSON",
                extra={"error": str(e)},
            )
            return []
        except Exception as e:
            logger.exception(
                "Limitation identification failed",
                extra={"error": str(e)},
            )
            return []

    async def suggest_counterarguments(self, claim: str, context: str = "") -> list[str]:
        """
        Generate potential counterarguments to a specific claim.

        Args:
            claim: The claim to counter
            context: Additional context

        Returns:
            List of counterarguments
        """
        context_hint = f"\n【コンテキスト】\n{context[:3000]}" if context else ""

        prompt = f"""以下の主張に対する反論を3つ生成してください。
{context_hint}

【主張】
{claim}

建設的で学術的な反論を、それぞれ2-3文で述べてください。
番号付きリストで出力してください。"""

        try:
            response = await self.ai_provider.generate(prompt)
            # Parse numbered list
            lines = response.strip().split("\n")
            counterargs = []
            for line in lines:
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    # Remove numbering
                    cleaned = line.lstrip("0123456789.-) ").strip()
                    if cleaned:
                        counterargs.append(cleaned)
            logger.info(f"Generated {len(counterargs)} counterarguments")
            return counterargs
        except Exception as e:
            logger.error(f"Counterargument generation failed: {e}")
            return []
