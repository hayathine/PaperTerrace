"""
論文の要約を生成する機能を提供するモジュール
"""

from src.logger import logger
from src.providers import get_ai_provider


class SummaryService:
    """Summary generation service for papers."""

    def __init__(self):
        self.ai_provider = get_ai_provider()

    async def summarize_full(self, text: str) -> str:
        """
        Generate a comprehensive summary of the entire paper.
        
        Args:
            text: The full paper text
            
        Returns:
            A structured summary in Japanese
        """
        prompt = f"""以下の論文を日本語で要約してください。

【論文テキスト】
{text[:15000]}

以下の形式で要約してください：

## 概要
（1-2文で論文の主題を説明）

## 主な貢献
（箇条書きで3-5点）

## 手法
（簡潔に研究手法を説明）

## 結論
（主要な発見と含意）
"""

        try:
            summary = await self.ai_provider.generate(prompt)
            logger.info("Full summary generated")
            return summary
        except Exception as e:
            logger.error(f"Summary generation failed: {e}")
            return f"要約の生成に失敗しました: {str(e)}"

    async def summarize_sections(self, text: str) -> list[dict]:
        """
        Generate section-by-section summaries.
        
        Args:
            text: The full paper text
            
        Returns:
            List of section summaries with title and content
        """
        prompt = f"""以下の論文を、セクションごとに要約してください。

【論文テキスト】
{text[:15000]}

各セクションについて、以下のJSON形式で出力してください：
[
  {{"section": "セクション名", "summary": "要約（2-3文）"}},
  ...
]

JSONのみを出力してください。"""

        try:
            response = await self.ai_provider.generate(prompt)
            # Try to parse JSON response
            import json
            # Clean up response if needed
            response = response.strip()
            if response.startswith("```"):
                response = response.split("```")[1]
                if response.startswith("json"):
                    response = response[4:]
            sections = json.loads(response)
            logger.info(f"Section summaries generated: {len(sections)} sections")
            return sections
        except json.JSONDecodeError:
            logger.warning("Failed to parse section summaries as JSON")
            return [{"section": "全体", "summary": response}]
        except Exception as e:
            logger.error(f"Section summary generation failed: {e}")
            return [{"section": "エラー", "summary": str(e)}]

    async def summarize_abstract(self, text: str) -> str:
        """
        Generate a one-paragraph abstract-style summary.
        
        Args:
            text: The paper text
            
        Returns:
            A concise abstract in Japanese
        """
        prompt = f"""以下の論文の要旨を、100-150字程度の日本語で作成してください。

{text[:10000]}

簡潔で学術的な文体で書いてください。"""

        try:
            abstract = await self.ai_provider.generate(prompt)
            logger.info("Abstract summary generated")
            return abstract
        except Exception as e:
            logger.error(f"Abstract generation failed: {e}")
            return f"要旨の生成に失敗しました: {str(e)}"
