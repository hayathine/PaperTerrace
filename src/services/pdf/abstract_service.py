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
                words = page.extract_words()

                # Find the word "abstract" (case-insensitive)
                abs_word = next(
                    (w for w in words if "abstract" in w["text"].lower().strip(".:")), None
                )

                if not abs_word:
                    logger.info("Word 'Abstract' not found on the first page.")
                    return None

                top = abs_word["top"]
                bottom = top + 500  # Reasonable height for an abstract
                left = 0
                right = page.width

                bbox = (left, top, right, bottom)
                try:
                    abstract_area = page.within_bbox(bbox)
                    abstract_text = abstract_area.extract_text()
                    if abstract_text:
                        return abstract_text.strip()
                except Exception as e:
                    logger.warning(f"Failed to extract text within bbox: {e}")

                return None
        except Exception as e:
            logger.error(f"pdfplumber extraction failed: {e}")
            return None
