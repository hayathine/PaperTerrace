"""
論文中の図表についての説明を生成する機能を提供するモジュール
"""

from src.logger import logger
from src.providers import get_ai_provider


class FigureInsightError(Exception):
    """Figure insight-specific exception."""

    pass


class FigureInsightService:
    """Figure and table insight service using vision AI."""

    def __init__(self):
        self.ai_provider = get_ai_provider()

    async def analyze_figure(
        self, image_bytes: bytes, caption: str = "", mime_type: str = "image/png"
    ) -> str:
        """
        Analyze a figure image and generate insights.

        Args:
            image_bytes: The image data
            caption: Optional figure caption
            mime_type: Image MIME type

        Returns:
            Analysis and insights in Japanese
        """
        caption_hint = f"\n【キャプション】\n{caption}" if caption else ""

        prompt = f"""この図（グラフ・表・図解）を分析し、以下の点について日本語で解説してください。
{caption_hint}

1. **図の種類と概要**: 何を表している図か
2. **主な発見**: 図から読み取れる主要な傾向やパターン
3. **データの解釈**: 数値やトレンドの意味
4. **含意**: この図が論文の主張をどのようにサポートしているか
5. **注目点**: 特に注目すべき点や異常値

視覚的な情報を言語化して、図を見なくても内容が理解できるように説明してください。"""

        try:
            logger.debug(
                "Analyzing figure",
                extra={"image_size": len(image_bytes), "mime_type": mime_type},
            )
            analysis = await self.ai_provider.generate_with_image(prompt, image_bytes, mime_type)
            analysis = analysis.strip()

            if not analysis:
                logger.warning("Empty figure analysis result")
                raise FigureInsightError("Empty analysis result")

            logger.info(
                "Figure analysis generated",
                extra={"output_length": len(analysis)},
            )
            return analysis
        except FigureInsightError:
            raise
        except Exception as e:
            logger.exception(
                "Figure analysis failed",
                extra={"error": str(e), "mime_type": mime_type},
            )
            return f"図の分析に失敗しました: {e}"

    async def analyze_table_text(self, table_text: str, context: str = "") -> str:
        """
        Analyze a table in text format.

        Args:
            table_text: The table content as text
            context: Surrounding text for context

        Returns:
            Analysis in Japanese
        """
        context_hint = f"\n【コンテキスト】\n{context[:1000]}" if context else ""

        prompt = f"""以下の表を分析し、日本語で解説してください。
{context_hint}

【表の内容】
{table_text}

以下の点について説明してください：
1. 表が示している内容の概要
2. 主要な数値やトレンド
3. 注目すべき比較や差異
4. この表から得られる結論"""

        try:
            analysis = await self.ai_provider.generate(prompt)
            logger.info("Table analysis generated")
            return analysis
        except Exception as e:
            logger.error(f"Table analysis failed: {e}")
            return f"表の分析に失敗しました: {str(e)}"

    async def compare_figures(self, description1: str, description2: str) -> str:
        """
        Compare two figures based on their descriptions.

        Args:
            description1: Description of first figure
            description2: Description of second figure

        Returns:
            Comparison analysis in Japanese
        """
        prompt = f"""以下の2つの図を比較し、その関係性や違いを分析してください。

【図1】
{description1}

【図2】
{description2}

比較ポイント：
1. 共通点
2. 相違点
3. 補完関係
4. 矛盾があれば指摘"""

        try:
            comparison = await self.ai_provider.generate(prompt)
            logger.info("Figure comparison generated")
            return comparison
        except Exception as e:
            logger.error(f"Figure comparison failed: {e}")
            return f"図の比較に失敗しました: {str(e)}"
