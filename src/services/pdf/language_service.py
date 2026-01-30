import fitz

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
            doc = fitz.open(stream=file_bytes, filetype="pdf")

            # 1. Metadata check
            catalog = doc.pdf_catalog()
            lang_entry = doc.xref_get_key(catalog, "Lang")
            if lang_entry[0] in ("name", "string") and lang_entry[1]:
                lang_code = lang_entry[1]
                logger.info(f"PDF Metadata Language detected: {lang_code}")
                language = lang_code.split("-")[0].lower()
                doc.close()
                return language

            # 2. AI prediction fallback
            if len(doc) > 0:
                text = doc[0].get_text()[:1000]
                if text.strip():
                    prompt = PDF_DETECT_LANGUAGE_PROMPT.format(text=text[:5000])
                    detected = await self.ai_provider.generate(prompt, model=self.model)
                    detected = detected.strip().lower()
                    if len(detected) == 2:
                        language = detected
                        logger.info(f"PDF Content Language detected by AI: {language}")

            doc.close()
        except Exception as e:
            logger.error(f"Language detection failed: {e}")

        return language
