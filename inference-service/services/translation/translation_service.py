"""
翻訳オーケストレーションサービス
確信度に基づく M2M100 と LlamaCpp (Qwen3) の切り替えを管理
"""

import logging

from .llamacpp_service import LlamaCppTranslationService
from .m2m100_service import M2M100TranslationService

logger = logging.getLogger(__name__)


class TranslationService:
    """翻訳統合サービス"""

    def __init__(
        self,
        m2m100_service: M2M100TranslationService,
        llamacpp_service: LlamaCppTranslationService,
    ):
        self.m2m100 = m2m100_service
        self.llamacpp = llamacpp_service

    async def initialize(self):
        """依存サービスの初期化（main.py側で初期化済みの場合はスキップ可能だが一応）"""
        if not self.m2m100.translator:
            await self.m2m100.initialize()
        if not self.llamacpp.llm:
            await self.llamacpp.initialize()

    async def translate(
        self, text: str, target_lang: str = "ja", paper_context: str = ""
    ) -> str:
        """M2M100を実行し、確信度が低い場合は LlamaCpp (Qwen3) にフォールバック"""

        # 1. M2M100翻訳
        res = await self.m2m100.translate(text, target_lang)
        translation = res["translation"]
        conf = res["conf"]
        model = res.get("model", "m2m100")

        logger.info(
            f"M2M100翻訳結果: {text} -> {translation} (conf={conf:.3f}, model={model})"
        )

        # 2. 確信度によるフォールバック
        if conf <= 0.5 and self.llamacpp:
            logger.info(
                f"確信度が低いため LlamaCpp (Qwen3) に切り替えます (conf={conf:.3f})"
            )
            return await self.llamacpp.translate_with_llamacpp(
                original_word=text,
                paper_context=paper_context or "No specific context available.",
                lang_name="Japanese" if target_lang == "ja" else "English",
            )

        return translation

    async def translate_batch(
        self, texts: list[str], target_lang: str = "ja", paper_context: str = ""
    ) -> list[str]:
        """バッチ翻訳の統合実行"""

        # 1. M2M100バッチ翻訳
        results = await self.m2m100.translate_batch(texts, target_lang)
        final_translations = []

        for i, res in enumerate(results):
            translation = res["translation"]
            conf = res["conf"]

            logger.info(
                f"M2M100バッチ翻訳[{i}]: {texts[i]} -> {translation} (conf={conf:.3f})"
            )

            if conf <= 0.5 and self.llamacpp:
                logger.info(
                    f"バッチ翻訳[{i}]の確信度が低いため LlamaCpp に切り替えます (conf={conf:.3f})"
                )
                translation = await self.llamacpp.translate_with_llamacpp(
                    original_word=texts[i],
                    paper_context=paper_context or "No specific context available.",
                    lang_name="Japanese" if target_lang == "ja" else "English",
                )

            final_translations.append(translation)

        return final_translations

    async def cleanup(self):
        await self.m2m100.cleanup()
        await self.llamacpp.cleanup()

    async def get_supported_languages(self) -> list[str]:
        from .utils import LANG_CODES

        return list(LANG_CODES.keys())
