import io

from common.logger import get_service_logger

log = get_service_logger("Language")


class LanguageService:
    def __init__(self, ai_provider, model: str):
        self.ai_provider = ai_provider
        self.model = model

    async def detect_language(self, file_bytes: bytes) -> str:
        """Detect PDF language using metadata or AI prediction."""
        language = "en"  # default

        try:
            import pdfplumber  # noqa: PLC0415 (遅延インポート: 起動時メモリ削減)
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                # 1. Metadata check
                metadata = pdf.metadata
                if metadata and "Language" in metadata:
                    lang_code = metadata["Language"]
                    language = lang_code.split("-")[0].lower()
                    log.info("detect", "Language from metadata", language=language)
                    return language

        except Exception as e:
            log.error("detect", "Language detection failed", error=str(e))

        return language
