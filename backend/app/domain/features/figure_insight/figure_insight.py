import os

from app.providers import get_ai_provider
from app.schemas.gemini_schema import (
    FigureAnalysisResponse,
)
from common.dspy.config import setup_dspy
from common.dspy.modules import VisionFigureModule
from common.logger import logger


class FigureInsightService:
    """Vision AIを使用した図表分析サービス"""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = os.getenv("FIGURE_EXPLAIN_MODEL", "gemini-2.5-flash-lite")
        setup_dspy()
        self.figure_mod = VisionFigureModule()

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
        from app.domain.features.correspondence_lang_dict import SUPPORTED_LANGUAGES

        caption_hint = f"\n[Caption]\n{caption}" if caption else ""
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        from common.prompts import VISION_ANALYZE_FIGURE_PROMPT

        prompt = VISION_ANALYZE_FIGURE_PROMPT.format(
            lang_name=lang_name, caption_hint=caption_hint
        )

        try:
            logger.debug(
                "Analyzing figure",
                extra={"image_size": len(image_bytes), "mime_type": mime_type},
            )
            analysis: FigureAnalysisResponse = (
                await self.ai_provider.generate_with_image(
                    prompt,
                    image_bytes,
                    mime_type,
                    model=self.model,
                    response_model=FigureAnalysisResponse,
                )
            )

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
