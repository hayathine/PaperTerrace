"""
スマート要約機能を提供するモジュール
論文全体、セクション別、アブストラクト形式の要約を生成
"""

import json

from src.logger import logger
from src.providers import get_ai_provider


class SummaryError(Exception):
    """Summary-specific exception."""

    pass


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
            logger.debug(
                "Generating full summary",
                extra={"text_length": len(text)},
            )
            summary = await self.ai_provider.generate(prompt)
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
            logger.debug(
                "Generating section summary",
                extra={"text_length": len(text)},
            )
            response = await self.ai_provider.generate(prompt)
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
