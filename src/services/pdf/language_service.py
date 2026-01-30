import io

import pdfplumber

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
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                # 1. Metadata check
                logger.debug("[LanguageService] Checking PDF metadata for language")
                metadata = pdf.metadata
                if metadata and "Language" in metadata:
                    lang_code = metadata["Language"]
                    language = lang_code.split("-")[0].lower()
                    logger.info(f"[LanguageService] Language detected from Metadata: {language}")
                    return language

                # 2. AI prediction fallback
                logger.info(
                    "[LanguageService] Metadata language missing. Falling back to AI detection"
                )
                if len(pdf.pages) > 0:
                    page = pdf.pages[0]
                    text = page.extract_text(use_text_flow=True) or ""
                    text = text.strip()
                    if text:
                        logger.debug(
                            f"[LanguageService] Analyzing first 1000 chars: {text[:100]}..."
                        )
                        prompt = PDF_DETECT_LANGUAGE_PROMPT.format(text=text[:5000])
                        detected = await self.ai_provider.generate(prompt, model=self.model)
                        detected = detected.strip().lower()
                        # Expecting 2-letter code (en, ja, etc)
                        if len(detected) <= 5:  # allow en-US or ja
                            language = detected.split("-")[0]
                            logger.info(f"[LanguageService] Language detected by AI: {language}")
                        else:
                            logger.warning(
                                f"[LanguageService] AI returned unexpected language format: {detected}"
                            )
                    else:
                        logger.warning(
                            "[LanguageService] Could not extract text from first page for language detection"
                        )
                else:
                    logger.warning("[LanguageService] PDF has no pages")

        except Exception as e:
            logger.error(f"[LanguageService] Language detection failed: {e}")

        return language
