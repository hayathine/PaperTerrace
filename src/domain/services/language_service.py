import io

import pdfplumber

from src.domain.prompts import PDF_DETECT_LANGUAGE_PROMPT
from src.logger import get_service_logger

log = get_service_logger("Language")


class LanguageService:
    def __init__(self, ai_provider, model: str):
        self.ai_provider = ai_provider
        self.model = model

    async def detect_language(self, file_bytes: bytes) -> str:
        """Detect PDF language using metadata or AI prediction."""
        language = "en"  # default

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                # 1. Metadata check
                metadata = pdf.metadata
                if metadata and "Language" in metadata:
                    lang_code = metadata["Language"]
                    language = lang_code.split("-")[0].lower()
                    log.info("detect", "Language from metadata", language=language)
                    return language

                # 2. AI prediction fallback
                log.info("detect", "Metadata missing, using AI detection")
                if len(pdf.pages) > 0:
                    page = pdf.pages[0]
                    text = page.extract_text() or ""
                    text = text.strip()
                    if text:
                        prompt = PDF_DETECT_LANGUAGE_PROMPT.format(text=text[:1000])
                        detected = await self.ai_provider.generate(prompt, model=self.model)
                        detected = detected.strip().lower()
                        if len(detected) <= 5:
                            language = detected.split("-")[0]
                            log.info("detect", "Language detected by AI", language=language)
                        else:
                            log.warning("detect", "Unexpected AI response", response=detected)
                    else:
                        log.warning("detect", "No text on first page")
                else:
                    log.warning("detect", "PDF has no pages")

        except Exception as e:
            log.error("detect", "Language detection failed", error=str(e))

        return language
