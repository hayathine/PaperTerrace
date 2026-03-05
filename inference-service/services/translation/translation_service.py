"""
翻訳オーケストレーションサービス
確信度に基づく M2M100 と LlamaCpp (Qwen3) の切り替えを管理
"""

import logging
import os

from .llamacpp_service import LlamaCppTranslationService
from .m2m100_service import M2M100TranslationService

logger = logging.getLogger(__name__)


class TranslationService:
    """翻訳統合サービス"""

    def __init__(
        self,
        m2m100_service: M2M100TranslationService | None,
        llamacpp_service: LlamaCppTranslationService | None,
        inference_type: str = "translation",
    ):
        self.m2m100 = m2m100_service
        self.llamacpp = llamacpp_service
        self.inference_type = inference_type
        self.fallback_threshold = float(
            os.getenv("TRANSLATION_FALLBACK_THRESHOLD", "0.5")
        )

    async def initialize(self):
        """依存サービスの初期化（main.py側で初期化済みの場合はスキップ可能だが一応）"""
        if self.m2m100 and not self.m2m100.translator:
            await self.m2m100.initialize()
        if self.llamacpp and not self.llamacpp.llm:
            await self.llamacpp.initialize()

    async def translate(
        self, text: str, target_lang: str = "ja", paper_context: str = ""
    ) -> tuple[str, str]:
        """指定された推論タイプに基づいて翻訳を実行"""

        from .utils import get_lang_name

        lang_full_name = get_lang_name(target_lang)

        # Qwen 単独モードの場合
        if self.inference_type == "qwen":
            if not self.llamacpp:
                raise ValueError(
                    "LlamaCpp service is not initialized but inference_type is qwen"
                )
            try:
                llm_result = await self.llamacpp.translate_with_llamacpp(
                    original_word=text,
                    paper_context=paper_context or "No specific context available.",
                    lang_name=lang_full_name,
                )
                return llm_result, "Qwen"
            except Exception as e:
                logger.error(f"Qwen3 translation failed: {e}")
                raise

        # M2M100 または translation (両方) モードの場合
        if not self.m2m100:
            raise ValueError("M2M100 service is not initialized")

        # 1. M2M100翻訳
        res = await self.m2m100.translate(text, target_lang)
        translation = res["translation"]
        conf = res["conf"]
        model = res.get("model", "m2m100")

        logger.info(
            f"M2M100翻訳結果: {text[:30]}... -> {translation[:30]}... (conf={conf:.3f}, target={target_lang}, model={model})"
        )

        # 2. 確信度によるフォールバック (translation モードのみ)
        if (
            conf <= self.fallback_threshold
            and self.llamacpp
            and self.inference_type in ["translation", "all"]
        ):
            logger.info(
                f"確信度が低いため LlamaCpp (Qwen3) に切り替えます (conf={conf:.3f}, target_lang={target_lang} -> {lang_full_name})"
            )
            try:
                llm_result = await self.llamacpp.translate_with_llamacpp(
                    original_word=text,
                    paper_context=paper_context or "No specific context available.",
                    lang_name=lang_full_name,
                )
                return llm_result, "Qwen"
            except Exception as e:
                # Qwen3 が失敗した場合、m2m100の結果をそのまま返す
                logger.warning(
                    f"Qwen3翻訳失敗 (conf={conf:.3f})、m2m100の結果を使用します: {e}"
                )

        return translation, model

    async def translate_batch(
        self, texts: list[str], target_lang: str = "ja", paper_context: str = ""
    ) -> tuple[list[str], list[str]]:
        """バッチ翻訳の統合実行"""
        from .utils import get_lang_name

        lang_full_name = get_lang_name(target_lang)

        # Qwen 単独モードの場合
        if self.inference_type == "qwen":
            final_translations = []
            final_models = []
            for text in texts:
                try:
                    translation = await self.llamacpp.translate_with_llamacpp(
                        original_word=text,
                        paper_context=paper_context or "No specific context available.",
                        lang_name=lang_full_name,
                    )
                    final_translations.append(translation)
                    final_models.append("Qwen")
                except Exception as e:
                    logger.warning(f"Qwen3 batch translation failed: {e}")
                    final_translations.append("")
                    final_models.append("failed")
            return final_translations, final_models

        # 1. M2M100バッチ翻訳
        results = await self.m2m100.translate_batch(texts, target_lang)
        final_translations = []
        final_models = []

        for i, res in enumerate(results):
            translation = res["translation"]
            conf = res["conf"]
            model = res.get("model", "m2m100")

            logger.info(
                f"M2M100バッチ翻訳[{i}]: {texts[i][:30]}... -> {translation[:30]}... (conf={conf:.3f})"
            )

            if (
                conf <= self.fallback_threshold
                and self.llamacpp
                and self.inference_type in ["translation", "all"]
            ):
                logger.info(
                    f"バッチ翻訳[{i}]の確信度が低いため LlamaCpp に切り替えます (conf={conf:.3f}, target={lang_full_name})"
                )
                try:
                    translation = await self.llamacpp.translate_with_llamacpp(
                        original_word=texts[i],
                        paper_context=paper_context or "No specific context available.",
                        lang_name=lang_full_name,
                    )
                    model = "Qwen"
                except Exception as e:
                    # Qwen3 が失敗した場合、m2m100の結果をそのまま使用
                    logger.warning(
                        f"バッチ翻訳[{i}] Qwen3失敗、m2m100の結果を使用します: {e}"
                    )

            final_translations.append(translation)
            final_models.append(model)

        return final_translations, final_models

    async def cleanup(self):
        if self.m2m100:
            await self.m2m100.cleanup()
        if self.llamacpp:
            await self.llamacpp.cleanup()

    async def get_supported_languages(self) -> list[str]:
        from .utils import LANG_CODES

        return list(LANG_CODES.keys())
