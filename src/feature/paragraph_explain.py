"""
パラグラフ単位で詳細な説明を生成する機能を提供するモジュール
"""

from src.logger import logger
from src.providers import get_ai_provider


class ParagraphExplainError(Exception):
    """Paragraph explanation-specific exception."""

    pass


class ParagraphExplainService:
    """Paragraph explanation service for deep understanding."""

    def __init__(self):
        self.ai_provider = get_ai_provider()

    async def explain(self, paragraph: str, full_context: str = "") -> str:
        """
        Generate a detailed explanation of a paragraph.

        Args:
            paragraph: The paragraph to explain
            full_context: The full paper text for context

        Returns:
            Detailed explanation in Japanese
        """
        context_hint = ""
        if full_context:
            context_hint = f"""
【論文全体のコンテキスト（抜粋）】
{full_context[:5000]}
"""

        prompt = f"""以下の段落を詳細に解説してください。
{context_hint}
【解説対象の段落】
{paragraph}

以下の点を含めて、日本語で分かりやすく解説してください：

1. **主張**: この段落で述べられている主な主張や内容
2. **背景知識**: 理解に必要な前提知識や専門用語の説明
3. **論理展開**: 議論がどのように展開されているか
4. **重要ポイント**: 特に注目すべき点や含意

専門的な内容も、大学院生が理解できるレベルで説明してください。"""

        try:
            logger.debug(
                "Generating paragraph explanation",
                extra={"paragraph_length": len(paragraph)},
            )
            explanation = await self.ai_provider.generate(prompt)
            explanation = explanation.strip()

            if not explanation:
                logger.warning("Empty paragraph explanation result")
                raise ParagraphExplainError("Empty explanation result")

            logger.info(
                "Paragraph explanation generated",
                extra={"input_length": len(paragraph), "output_length": len(explanation)},
            )
            return explanation
        except ParagraphExplainError:
            raise
        except Exception as e:
            logger.exception(
                "Paragraph explanation failed",
                extra={"error": str(e)},
            )
            return f"解説の生成に失敗しました: {e}"

    async def explain_terminology(
        self, paragraph: str, terms: list[str] | None = None
    ) -> list[dict]:
        """
        Extract and explain technical terms in a paragraph.

        Args:
            paragraph: The paragraph to analyze
            terms: Optional list of specific terms to explain

        Returns:
            List of term explanations
        """
        terms_hint = ""
        if terms:
            terms_hint = f"特に以下の用語を優先的に説明してください：{', '.join(terms)}"

        prompt = f"""以下の段落から専門用語を抽出し、それぞれを簡潔に説明してください。

【段落】
{paragraph}

{terms_hint}

以下のJSON形式で出力してください：
[
  {{"term": "用語", "explanation": "簡潔な説明（1-2文）", "importance": "high/medium/low"}}
]

最大10件まで。JSONのみを出力してください。"""

        try:
            response = await self.ai_provider.generate(prompt)
            import json

            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            terms_explained = json.loads(response)
            logger.info(f"Explained {len(terms_explained)} terms")
            return terms_explained
        except Exception as e:
            logger.error(f"Terminology explanation failed: {e}")
            return []
