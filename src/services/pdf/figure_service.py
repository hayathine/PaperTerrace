import base64
from typing import Any, Dict, List

import fitz

from src.logger import logger
from src.prompts import VISION_DETECT_ITEMS_PROMPT
from src.providers.image_storage import save_page_image
from src.schemas.figure import FigureDetectionResponse


class FigureService:
    def __init__(self, ai_provider, model: str):
        self.ai_provider = ai_provider
        self.model = model

    async def detect_and_extract_figures(
        self, img_bytes: bytes, pix: fitz.Pixmap, file_hash: str, page_num: int
    ) -> List[Dict[str, Any]]:
        """
        Detect figures/tables using AI and extract them as separate images.
        """
        try:
            detection_result: FigureDetectionResponse = await self.ai_provider.generate_with_image(
                VISION_DETECT_ITEMS_PROMPT,
                img_bytes,
                "image/png",
                response_model=FigureDetectionResponse,
                model=self.model,
            )

            found_figures = detection_result.figures if detection_result else []
            if not found_figures:
                return []

            logger.info(f"[FigureService] Detected {len(found_figures)} items on page {page_num}")

            figures_data = []
            page_w = pix.width
            page_h = pix.height

            for i, fig in enumerate(found_figures):
                try:
                    # box_2d is [ymin, xmin, ymax, xmax] normalized 0-1
                    ymin, xmin, ymax, xmax = fig.box_2d

                    # Convert to pixels (PyMuPDF Rect: x0, y0, x1, y1)
                    r_xmin = int(xmin * page_w)
                    r_ymin = int(ymin * page_h)
                    r_xmax = int(xmax * page_w)
                    r_ymax = int(ymax * page_h)

                    # Clip to page bounds
                    r_xmin = max(0, r_xmin)
                    r_ymin = max(0, r_ymin)
                    r_xmax = min(page_w, r_xmax)
                    r_ymax = min(page_h, r_ymax)

                    # Skip invalid or tiny boxes
                    if (r_xmax - r_xmin) < 10 or (r_ymax - r_ymin) < 10:
                        continue

                    # Crop from the original page pixmap
                    crop_rect = fitz.IRect(r_xmin, r_ymin, r_xmax, r_ymax)
                    crop_pix = fitz.Pixmap(pix, crop_rect)
                    crop_bytes = crop_pix.tobytes("png")

                    if len(crop_bytes) < 500:
                        continue

                    crop_b64 = base64.b64encode(crop_bytes).decode("utf-8")

                    # Save figure image
                    figure_img_name = f"figure_{page_num}_{i}_{fig.label}"
                    figure_url = save_page_image(file_hash, figure_img_name, crop_b64)

                    figures_data.append(
                        {
                            "image_url": figure_url,
                            "bbox": [r_xmin, r_ymin, r_xmax, r_ymax],
                            "explanation": "",
                            "page_num": page_num,
                            "label": fig.label,
                        }
                    )

                except Exception as e:
                    logger.warning(f"[FigureService] Crop failed for item {i} on p.{page_num}: {e}")

            return figures_data

        except Exception as e:
            logger.warning(f"[FigureService] Detection failed on p.{page_num}: {e}")
            return []
