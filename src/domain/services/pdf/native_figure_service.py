import io
from typing import Any, Dict, List

import pdfplumber
from PIL import Image

from src.core.logger import logger


class NativeFigureService:
    """Service to extract 'native' figures (embedded images) from PDF using pdfplumber."""

    def extract_figures(
        self,
        pdf_bytes: bytes,
        page_num: int,
        page_image: Image.Image,
    ) -> List[Dict[str, Any]]:
        """
        Extract figure coordinates from PDF metadata.
        Coordinates are scaled to match the provided PIL Image (pixels).
        """
        native_figures = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                if page_num > len(pdf.pages):
                    return []

                page = pdf.pages[page_num - 1]

                # Calculate scale factors between PDF points and Image pixels
                # Use float for precision
                scale_x = page_image.width / float(page.width)
                scale_y = page_image.height / float(page.height)

                # Each 'img' in page.images is a dict containing x0, top, x1, bottom, etc.
                for img in page.images:
                    xmin = img["x0"] * scale_x
                    ymin = img["top"] * scale_y
                    xmax = img["x1"] * scale_x
                    ymax = img["bottom"] * scale_y

                    # Filter out tiny elements (like icons or small decorative lines)
                    width = xmax - xmin
                    height = ymax - ymin
                    if width < 20 or height < 20:
                        continue

                    native_figures.append(
                        {
                            "bbox": [xmin, ymin, xmax, ymax],
                            "label": "Figure",
                            "confidence": 1.0,  # Native coordinates are 100% certain
                        }
                    )

            if native_figures:
                logger.debug(
                    f"[NativeFigureService] Found {len(native_figures)} native figures on p.{page_num}"
                )

            return native_figures

        except Exception as e:
            logger.warning(
                f"[NativeFigureService] Failed to extract figures from p.{page_num}: {e}"
            )
            return []


native_figure_service = NativeFigureService()
