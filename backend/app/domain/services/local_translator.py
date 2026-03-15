"""
ローカル翻訳サービス（後方互換インターフェース）
翻訳処理はGeminiに統合済み。このクラスは互換性のため保持。
"""

from app.providers.inference_client import InferenceServiceDownError
from common.logger import ServiceLogger

log = ServiceLogger("LocalTranslator")


class LocalTranslator:
    """
    翻訳サービスのスタブ（互換性保持用）
    実際の翻訳はtranslation.pyのGeminiフローで処理される。
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
        log.info("init", "LocalTranslator initialized (Gemini-only mode)")

    async def prewarm(self):
        """ウォームアップ（翻訳はGemini統合済みのためスキップ）"""
        pass

    async def translate_async(
        self,
        text: str,
        tgt_lang: str = "ja",
        paper_context: str | None = None,
        original_text: str | None = None,
    ) -> tuple[str, str | None, str | None]:
        """
        翻訳はGeminiに統合済み。呼び出し元はGeminiフォールバックへ進む。
        """
        raise InferenceServiceDownError(
            "LocalTranslator is deprecated. Use Gemini translation directly."
        )

    def translate(
        self, text: str, src_lang: str = "en", tgt_lang: str = "ja"
    ) -> str | None:
        """同期版（非推奨）"""
        return text


def get_local_translator():
    return LocalTranslator()
