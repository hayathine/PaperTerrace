from typing import List, Optional

from pydantic import BaseModel, Field

from src.logger import logger
from src.providers import get_ai_provider


class FigureAnalysisResponse(BaseModel):
    """画像分析結果の構造化データモデル"""

    type_overview: str = Field(..., description="What this figure represents")
    key_findings: List[str] = Field(..., description="Main trends or patterns observed")
    interpretation: str = Field(..., description="Meaning of the numbers or trends")
    implications: str = Field(..., description="How this supports the paper's claims")
    highlights: List[str] = Field(..., description="Notable points or anomalies")


class TableAnalysisResponse(BaseModel):
    """表分析結果の構造化データモデル"""

    overview: str = Field(..., description="Overview of what the table shows")
    key_numbers: List[str] = Field(..., description="Key numbers and trends")
    comparisons: List[str] = Field(..., description="Notable comparisons or differences")
    conclusions: str = Field(..., description="Conclusions drawn from this table")


class FigureComparisonResponse(BaseModel):
    """図表比較結果の構造化データモデル"""

    similarities: List[str] = Field(..., description="Similarities between the two figures")
    differences: List[str] = Field(..., description="Differences between the two figures")
    relationship: str = Field(..., description="Complementary or other relationship")
    contradictions: Optional[List[str]] = Field(None, description="Contradictions if any")


class FigureInsightService:
    """Figure and table insight service using vision AI."""

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
        Analyze a figure image and generate insights.

        Args:
            image_bytes: The image data
            caption: Optional figure caption
            mime_type: Image MIME type
            target_lang: Output language

        Returns:
            Analysis and insights in target language
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

            # 既存のコードが文字列を期待している可能性があるが、
            # フロントエンド側での表示を考慮して、整形されたテキストを返すか、
            # あるいはAPIエンドポイント側で調整する必要がある。
            # ここではサービスとして構造化データを文字列に変換して返す（後方互換性のため）
            # もしAPIエンドポイントも修正するなら、辞書をそのまま返しても良い。

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
        Analyze a table in text format.

        Args:
            table_text: The table content as text
            context: Surrounding text for context
            target_lang: Output language

        Returns:
            Analysis in target language
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
        Compare two figures based on their descriptions.

        Args:
            description1: Description of first figure
            description2: Description of second figure
            target_lang: Output language

        Returns:
            Comparison analysis in target language
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
