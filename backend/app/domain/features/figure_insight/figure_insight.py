from app.domain.features.cache_utils import PDF_CACHE_MODEL, get_pdf_cache_key
from app.providers import get_ai_provider
from app.schemas.gemini_schema import (
    FigureAnalysisResponse,
)
from common import settings
from common.dspy_utils.trace import TraceContext, save_trace
from common.logger import ServiceLogger
from redis_provider.provider import RedisService

log = ServiceLogger("FigureInsight")


class FigureInsightService:
    """Vision AIを使用した図表分析サービス"""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = settings.get("FIGURE_EXPLAIN_MODEL", "gemini-2.5-flash")
        self.redis = RedisService()

    async def analyze_figure(
        self,
        image_bytes: bytes | None = None,
        caption: str = "",
        mime_type: str = "image/jpeg",
        target_lang: str = "ja",
        user_id: str | None = None,
        session_id: str | None = None,
        paper_id: str | None = None,
        image_uri: str | None = None,
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

        from common.dspy_seed_prompt import VISION_ANALYZE_FIGURE_PROMPT

        prompt = VISION_ANALYZE_FIGURE_PROMPT.format(
            lang_name=lang_name, caption_hint=caption_hint
        )

        # paper_id に紐づく PDF コンテキストキャッシュを Redis から取得（共有モデルのキー）
        pdf_cache_name: str | None = None
        if paper_id:
            pdf_cache_name = self.redis.get(get_pdf_cache_key(paper_id))

        import time

        start = time.perf_counter()
        try:
            log.debug(
                "analyze",
                "Analyzing figure",
                image_size=len(image_bytes) if image_bytes else 0,
                image_uri=image_uri,
                mime_type=mime_type,
                using_pdf_cache=pdf_cache_name is not None,
            )
            log.debug(
                "analyze",
                "Calling AI provider with timeout",
                timeout=20,
            )
            import asyncio

            try:
                analysis: FigureAnalysisResponse = await asyncio.wait_for(
                    self.ai_provider.generate_with_image(
                        prompt,
                        image_bytes=image_bytes,
                        mime_type=mime_type,
                        model=PDF_CACHE_MODEL if pdf_cache_name else self.model,
                        response_model=FigureAnalysisResponse,
                        image_uri=image_uri,
                        max_tokens=4096,
                        cached_content_name=pdf_cache_name,
                    ),
                    timeout=20.0,  # Vision AI は時間がかかるため長めに設定
                )
            except asyncio.TimeoutError:
                log.error("analyze", "AI provider analysis timed out", timeout=90)
                raise Exception(
                    "AI分析がタイムアウトしました。もう一度お試しください。"
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

            elapsed_ms = int((time.perf_counter() - start) * 1000)
            save_trace(
                module_name="VisionFigureModule",
                signature="VisionAnalyzeFigure",
                inputs={
                    "caption_hint": caption_hint,
                    "lang_name": lang_name,
                    "image_uri": image_uri or "",
                },
                outputs=analysis.model_dump(),
                latency_ms=elapsed_ms,
                context=TraceContext(
                    user_id=user_id, session_id=session_id, paper_id=paper_id
                ),
            )

            log.info(
                "analyze",
                "Figure analysis generated",
                output_length=len(formatted_text),
                user_id=user_id,
                session_id=session_id,
                paper_id=paper_id,
            )
            return formatted_text

        except Exception as e:
            elapsed_ms = int((time.perf_counter() - start) * 1000)
            save_trace(
                module_name="VisionFigureModule",
                signature="VisionAnalyzeFigure",
                inputs={
                    "caption_hint": caption_hint,
                    "lang_name": lang_name,
                    "image_uri": image_uri or "",
                },
                outputs={},
                latency_ms=elapsed_ms,
                is_success=False,
                error_msg=str(e),
                context=TraceContext(
                    user_id=user_id, session_id=session_id, paper_id=paper_id
                ),
            )
            log.exception(
                "analyze",
                "Figure analysis failed",
                mime_type=mime_type,
            )
            return f"図の分析に失敗しました: {e}"
