"""
ローカル翻訳サービス（ServiceB連携版）
翻訳処理をServiceBに委譲し、ServiceAは結果の取得のみを行う
"""

import os

import httpx
from app.domain.features.correspondence_lang_dict import SUPPORTED_LANGUAGES
from app.domain.prompts import DICT_TRANSLATE_WORD_SIMPLE_PROMPT
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
        非同期翻訳
        - TRANSLATION_BACKEND="custom": Cloudflare Tunnel経由のカスタム翻訳
        - TRANSLATION_BACKEND="service_b" (default): ServiceB (Inference Service) 経由
        """
        if not text.strip():
            return ""

        custom_url = os.getenv(
            "CUSTOM_TRANSLATION_URL",
            "https://sizes-stranger-expertise-perfume.trycloudflare.com",
        )

        # Check if we should use custom backend
        use_custom = os.getenv("USE_CUSTOM_TRANSLATION", "true").lower() == "true"

        if use_custom and custom_url:
            return await self._translate_via_custom(text, tgt_lang, custom_url)
        else:
            return await self._translate_via_service_b(text, tgt_lang)

    async def _translate_via_custom(self, text: str, tgt_lang: str, url: str) -> str:
        try:
            log.debug("translate_async", f"Translating via Custom: {text[:50]}...")

            # プロンプトの構築
            lang_name = SUPPORTED_LANGUAGES.get(tgt_lang, tgt_lang)
            prompt = DICT_TRANSLATE_WORD_SIMPLE_PROMPT.format(
                paper_context="", lemma=text, lang_name=lang_name
            )

            payload = {"prompt": prompt}

            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, timeout=30.0)
                response.raise_for_status()

                # 1. JSONとして解析を試みる
                try:
                    data = response.json()

                    # レスポンスから翻訳結果を抽出 (柔軟に対応)
                    translation = (
                        data.get("content")
                        or data.get("text")
                        or data.get("translation")
                        or data.get("response")
                        or ""
                    )

                    # OpenAI互換フォーマットの考慮
                    if not translation and "choices" in data:
                        try:
                            translation = data["choices"][0]["message"]["content"]
                        except (IndexError, KeyError):
                            pass

                    if translation:
                        log.debug(
                            "translate_async",
                            f"Custom Translation result: {translation[:50]}...",
                        )
                        return translation.strip()

                except Exception as json_err:
                    log.debug(
                        "translate_async",
                        f"Custom response is not valid JSON: {json_err}. Trying raw text.",
                    )

                # 2. Raw Textとして利用を試みる (JSON解析失敗時 or JSON内に翻訳が見つからない場合)
                if response.text and response.text.strip():
                    log.debug(
                        "translate_async",
                        f"Custom Translation result (raw text): {response.text[:50]}...",
                    )
                    return response.text.strip()

                log.warning(
                    "translate_async", "No translation found in custom response"
                )
                return text

        except Exception as e:
            log.error("translate_async", f"Custom Translation error: {e}")
            return text

    async def _translate_via_service_b(self, text: str, tgt_lang: str) -> str:
        try:
            log.debug("translate_async", f"Translating via ServiceB: {text[:50]}...")

            client = await get_inference_client()
            translation = await client.translate_text(text, tgt_lang)

            log.debug(
                "translate_async", f"ServiceB Translation result: {translation[:50]}..."
            )
            return translation

        except CircuitBreakerError as e:
            log.error("translate_async", f"Circuit breaker error: {e}")
            return text

        except InferenceServiceError as e:
            log.error("translate_async", f"Inference service error: {e}")
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
