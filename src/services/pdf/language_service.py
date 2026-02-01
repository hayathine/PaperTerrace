import io

from pypdf import PdfReader

from src.logger import logger
from src.prompts import PDF_DETECT_LANGUAGE_PROMPT


class LanguageService:
    def __init__(self, ai_provider, model: str):
        self.ai_provider = ai_provider
        self.model = model

    async def detect_language(self, file_bytes: bytes) -> str:
        """Detect PDF language using metadata or AI prediction."""
        language = "en"  # default

        try:
            reader = PdfReader(io.BytesIO(file_bytes))

            # 1. Metadata check
            metadata = reader.metadata
            if metadata and "/Lang" in metadata:
                lang_code = str(metadata["/Lang"])
                logger.info(f"PDF Metadata Language detected: {lang_code}")
                return lang_code.split("-")[0].lower()

            # 2. AI prediction fallback
            if len(reader.pages) > 0:
                text = reader.pages[0].extract_text()[:1000]
                if text and text.strip():
                    prompt = PDF_DETECT_LANGUAGE_PROMPT.format(text=text[:5000])
                    detected = await self.ai_provider.generate(prompt, model=self.model)
                    detected = detected.strip().lower()
                    if len(detected) == 2:
                        language = detected
                        logger.info(f"PDF Content Language detected by AI: {language}")

        except Exception as e:
            logger.error(f"Language detection failed: {e}")

        return language
