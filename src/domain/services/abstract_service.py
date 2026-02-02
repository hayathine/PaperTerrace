import io
from typing import Optional

from src.logger import logger


class AbstractService:
    @staticmethod
    def extract_abstract(file_bytes: bytes) -> Optional[str]:
        """
        Extract the abstract text from the first page using pdfplumber coordinates.
        """
        import pdfplumber

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if not pdf.pages:
                    return None
                page = pdf.pages[0]
                words = page.extract_words(use_text_flow=True)

                # Find the word "abstract" (case-insensitive)
                logger.debug("[AbstractService] Searching for 'Abstract' keyword on first page")
                abs_word = next(
                    (w for w in words if "abstract" in w["text"].lower().strip(".:")), None
                )

                if not abs_word:
                    logger.info("[AbstractService] Keyword 'Abstract' not found on p.1")
                    return None

                logger.info(f"[AbstractService] Found 'Abstract' keyword at y={abs_word['top']}")
                top = abs_word["top"]
                bottom = top + 800  # Increased range for longer abstracts
                left = 0
                right = page.width

                bbox = (left, top, right, bottom)
                try:
                    abstract_area = page.within_bbox(bbox)
                    abstract_text = abstract_area.extract_text()
                    if abstract_text:
                        logger.info(
                            f"[AbstractService] Extracted abstract (length: {len(abstract_text)})"
                        )
                        return abstract_text.strip()
                except Exception as e:
                    logger.warning(f"[AbstractService] Failed to extract text within bbox: {e}")

                logger.info("[AbstractService] No text found in identified abstract area")
                return None
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            return None
