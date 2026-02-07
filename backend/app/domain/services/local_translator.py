"""
ローカル翻訳サービス（ServiceB連携版）
翻訳処理をServiceBに委譲し、ServiceAは結果の取得のみを行う
"""

import os

from app.providers.inference_client import (
    CircuitBreakerError,
    InferenceServiceError,
    get_inference_client,
)

from common.logger import get_service_logger

log = get_service_logger("LocalTranslator")


class LocalTranslator:
    """
    ローカル翻訳サービス（ServiceB連携版）
    実際の翻訳処理はServiceBで実行し、このクラスはクライアントとして機能
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        self._initialized = True
        log.info("init", "LocalTranslator initialized (ServiceB client mode)")

    async def prewarm(self):
        """
        ServiceBのウォームアップ（ヘルスチェック）
        """
        # Skip inference service warmup if disabled
        if os.getenv("SKIP_INFERENCE_SERVICE_WARMUP", "false").lower() == "true":
            log.info(
                "prewarm", "Skipping ServiceB warmup (disabled by environment variable)"
            )
            return

        try:
            client = await get_inference_client()
            health_status = await client.health_check()
            log.info("prewarm", f"ServiceB health check: {health_status}")
        except Exception as e:
            log.warning("prewarm", f"ServiceB warmup failed: {e}")

    async def translate_async(self, text: str, tgt_lang: str = "ja") -> str | None:
        """
        非同期翻訳（ServiceB経由）
        """
        if not text.strip():
            return ""

        try:
            log.debug("translate_async", f"Translating: {text[:50]}...")

            client = await get_inference_client()
            translation = await client.translate_text(text, tgt_lang)

            log.debug("translate_async", f"Translation result: {translation[:50]}...")
            return translation

        except CircuitBreakerError as e:
            log.error("translate_async", f"Circuit breaker error: {e}")
            # フォールバック: 元のテキストを返す
            return text

        except InferenceServiceError as e:
            log.error("translate_async", f"Inference service error: {e}")
            # フォールバック: 元のテキストを返す
            return text

        except Exception as e:
            log.error("translate_async", f"Unexpected error: {e}")
            return text

    def translate(
        self, text: str, src_lang: str = "en", tgt_lang: str = "ja"
    ) -> str | None:
        """
        同期版翻訳（後方互換性のため保持）
        注意: この方法は非推奨。translate_asyncを使用してください。
        """
        log.warning(
            "translate",
            "Synchronous translation is deprecated. Use translate_async instead.",
        )

        # 同期版では元のテキストを返す（ServiceBは非同期のため）
        return text


def get_local_translator():
    return LocalTranslator()
