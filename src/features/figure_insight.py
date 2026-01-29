from typing import List, Optional

from pydantic import BaseModel, Field

from src.logger import logger
from src.providers import get_ai_provider


class FigureAnalysisResponse(BaseModel):
    """画像分析結果の構造化モデル"""

    type_overview: str = Field(..., description="図の概要と種類")
    key_findings: List[str] = Field(..., description="主な傾向やパターン")
    interpretation: str = Field(..., description="数値や傾向の解釈")
    implications: str = Field(..., description="論文の主張に対する裏付け")
    highlights: List[str] = Field(..., description="特筆すべき点や異常値")


class TableAnalysisResponse(BaseModel):
    """表分析結果の構造化モデル"""

    overview: str = Field(..., description="表の概要")
    key_numbers: List[str] = Field(..., description="重要な数値と傾向")
    comparisons: List[str] = Field(..., description="特筆すべき比較や差異")
    conclusions: str = Field(..., description="表から導かれる結論")


class FigureComparisonResponse(BaseModel):
    """図表比較結果の構造化モデル"""

    similarities: List[str] = Field(..., description="2つの図の類似点")
    differences: List[str] = Field(..., description="2つの図の相違点")
    relationship: str = Field(..., description="補完関係などの関連性")
    contradictions: Optional[List[str]] = Field(None, description="矛盾点（ある場合）")


class FigureInsightService:
    """Vision AIを使用した図表分析サービス"""

    def __init__(self):
        self.ai_provider = get_ai_provider()

    async def analyze_figure(
        self,
        image_bytes: bytes,
        caption: str = "",
        mime_type: str = "image/png",
        target_lang: str = "ja",
    ) -> str:
        """
        図表画像を分析し、洞察を生成する。

        Args:
            image_bytes: 画像データ
            caption: 図のキャプション（任意）
            mime_type: 画像のMIMEタイプ
            target_lang: 出力言語

        Returns:
            ターゲット言語での分析結果
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        caption_hint = f"\n[Caption]\n{caption}" if caption else ""

        prompt = f"""Analyze this figure (graph, table, or diagram) and explain the following points in {lang_name}.
{caption_hint}

1. **Type & Overview**: What this figure represents.
2. **Key Findings**: Main trends or patterns observed.
3. **Interpretation**: Meaning of the numbers or trends.
4. **Implications**: How this supports the paper's claims.
5. **Highlights**: Notable points or anomalies.

Verbalize visual information so it can be understood without seeing the figure.
Output in {lang_name}.
"""

        try:
            logger.debug(
                "Analyzing figure",
                extra={"image_size": len(image_bytes), "mime_type": mime_type},
            )
            analysis: FigureAnalysisResponse = await self.ai_provider.generate_with_image(
                prompt, image_bytes, mime_type, response_model=FigureAnalysisResponse
            )

            # NOTE: フロントエンド表示用に整形したテキストを返す
            result_lines = [
                f"### Type & Overview\n{analysis.type_overview}",
                "\n### Key Findings",
                *[f"- {item}" for item in analysis.key_findings],
                f"\n### Interpretation\n{analysis.interpretation}",
                f"\n### Implications\n{analysis.implications}",
                "\n### Highlights",
                *[f"- {item}" for item in analysis.highlights],
            ]
            formatted_text = "\n".join(result_lines)

            logger.info(
                "Figure analysis generated",
                extra={"output_length": len(formatted_text)},
            )
            return formatted_text
        except Exception as e:
            logger.exception(
                "Figure analysis failed",
                extra={"error": str(e), "mime_type": mime_type},
            )
            return f"図の分析に失敗しました: {e}"

    async def analyze_table_text(
        self, table_text: str, context: str = "", target_lang: str = "ja"
    ) -> str:
        """
        テキスト形式の表を分析する。

        Args:
            table_text: 表のテキスト内容
            context: 周辺コンテキスト
            target_lang: 出力言語

        Returns:
            ターゲット言語での分析結果
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        context_hint = f"\n[Context]\n{context[:1000]}" if context else ""

        prompt = f"""Analyze the following table and explain it in {lang_name}.
{context_hint}

[Table Content]
{table_text}

Please explain:
1. Overview of what the table shows.
2. Key numbers and trends.
3. Notable comparisons or differences.
4. Conclusions drawn from this table.

Output in {lang_name}.
"""

        try:
            analysis: TableAnalysisResponse = await self.ai_provider.generate(
                prompt, response_model=TableAnalysisResponse
            )

            result_lines = [
                f"### Overview\n{analysis.overview}",
                "\n### Key Numbers & Trends",
                *[f"- {item}" for item in analysis.key_numbers],
                "\n### Comparisons",
                *[f"- {item}" for item in analysis.comparisons],
                f"\n### Conclusions\n{analysis.conclusions}",
            ]
            formatted_text = "\n".join(result_lines)

            logger.info("Table analysis generated")
            return formatted_text
        except Exception as e:
            logger.error(f"Table analysis failed: {e}")
            return f"表の分析に失敗しました: {str(e)}"

    async def compare_figures(
        self, description1: str, description2: str, target_lang: str = "ja"
    ) -> str:
        """
        記述に基づいて2つの図を比較する。

        Args:
            description1: 図1の記述
            description2: 図2の記述
            target_lang: 出力言語

        Returns:
            比較分析結果
        """
        from .translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        prompt = f"""Compare the following two figures and analyze their relationship or differences in {lang_name}.

[Figure 1]
{description1}

[Figure 2]
{description2}

Comparison Points:
1. Similarities
2. Differences
3. Complementary relationship
4. Contradictions (if any)

Output in {lang_name}.
"""

        try:
            comparison: FigureComparisonResponse = await self.ai_provider.generate(
                prompt, response_model=FigureComparisonResponse
            )

            result_lines = [
                "### Similarities",
                *[f"- {item}" for item in comparison.similarities],
                "\n### Differences",
                *[f"- {item}" for item in comparison.differences],
                f"\n### Relationship\n{comparison.relationship}",
            ]
            if comparison.contradictions:
                result_lines.append("\n### Contradictions")
                result_lines.extend([f"- {item}" for item in comparison.contradictions])

            formatted_text = "\n".join(result_lines)

            logger.info("Figure comparison generated")
            return formatted_text
        except Exception as e:
            logger.error(f"Figure comparison failed: {e}")
            return f"図の比較に失敗しました: {str(e)}"
