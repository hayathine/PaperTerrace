import base64
import io
from typing import Any, Dict, List

# pdfplumber related imports for type hinting and functionality
from pdfplumber.display import PageImage
from pdfplumber.page import Page
from PIL import Image

from src.logger import logger
from src.providers.image_storage import save_page_image


class FigureService:
    def __init__(self, ai_provider, model: str):
        self.ai_provider = ai_provider
        self.model = model

    async def detect_and_extract_figures(
        self,
        img_bytes: bytes,
        page_img: PageImage,
        page: Page,
        file_hash: str,
        page_num: int,
        pypdf_page: Any = None,
    ) -> List[Dict[str, Any]]:
        """
        Detect figures/tables using AI and extract them as separate images.
        Also uses pdfplumber.images and pypdf.images to extract native images directly if available.
        """
        figures_data = []

        # 1. Native extraction (using pypdf with requested filtering)
        if pypdf_page and hasattr(pypdf_page, "images"):
            logger.debug(
                f"[FigureService] p.{page_num}: Attempting native image extraction with filtering"
            )
            try:
                # Step 3: Caption check
                # Note: 'page' is a pdfplumber Page object, extract_text() is efficient
                page_text = page.extract_text(use_text_flow=True) or ""
                caption_keywords = ["Figure", "Fig.", "FIG.", "図"]
                has_caption = any(k in page_text for k in caption_keywords)

                if not has_caption:
                    logger.debug(
                        f"[FigureService] p.{page_num}: No caption keyword found. Skipping native images."
                    )
                    return []

                found_count = 0
                for i, image_file in enumerate(pypdf_page.images):
                    img_data = image_file.data
                    if len(img_data) < 1000:
                        continue

                    # Step 1 & 2: Detect dimensions and filter (fast)
                    try:
                        # Using PIL to get dimensions from header
                        with Image.open(io.BytesIO(img_data)) as img:
                            width, height = img.size
                    except Exception:
                        continue

                    # 極端に小さい or バナーっぽい
                    if width < 100 or height < 100:
                        continue
                    if height > 0 and width / height > 5:
                        continue
                    # 1ページ目のバナー対策 (page_num 1-indexed)
                    if page_num == 1 and width < 300:
                        continue

                    # Save if passed filtering
                    img_b64 = base64.b64encode(img_data).decode("utf-8")
                    figure_img_name = f"native_img_{page_num}_{i}_{image_file.name}"
                    figure_url = save_page_image(file_hash, figure_img_name, img_b64)

                    figures_data.append(
                        {
                            "image_url": figure_url,
                            "bbox": [0, 0, 0, 0],
                            "explanation": "",
                            "page_num": page_num,
                            "label": "image",
                        }
                    )
                    found_count += 1

                if found_count > 0:
                    logger.info(
                        f"[FigureService] p.{page_num}: Extracted {found_count} filtered native images"
                    )
            except Exception as e:
                logger.warning(f"[FigureService] p.{page_num}: Native extraction failed: {e}")

        # Phase 2 & 3 (AI Detection) are skipped during initial processing.

        # 2. AI-based detection (finds composite figures, charts, and captions)
        # DEPRECATED: skipping during initial extraction to save costs/time.
        # Figure analysis is now on-demand via explain button.
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
                return figures_data

            logger.info(
                f"[FigureService] AI Detected {len(found_figures)} items on page {page_num}"
            )

            page_w, page_h = page.width, page.height

            for i, fig in enumerate(found_figures):
                try:
                    # box_2d is [ymin, xmin, ymax, xmax] normalized 0-1
                    ymin, xmin, ymax, xmax = fig.box_2d

                    # Convert normalized to page points
                    p_xmin = xmin * page_w
                    p_ymin = ymin * page_h
                    p_xmax = xmax * page_w
                    p_ymax = ymax * page_h

                    # Clip to page bounds
                    p_xmin = max(0, p_xmin)
                    p_ymin = max(0, p_ymin)
                    p_xmax = min(page_w, p_xmax)
                    p_ymax = min(page_h, p_ymax)

                    # Use page.crop() and then to_image()
                    # This is more robust than manual PIL cropping
                    cropped_page = page.crop((p_xmin, p_ymin, p_xmax, p_ymax))
                    crop_img_obj = cropped_page.to_image(resolution=150)
                    crop_pil = crop_img_obj.original

                    buffer = io.BytesIO()
                    crop_pil.save(buffer, format="PNG")
                    crop_bytes = buffer.getvalue()

                    if len(crop_bytes) < 500:
                        continue

                    crop_b64 = base64.b64encode(crop_bytes).decode("utf-8")
                    figure_img_name = f"figure_{page_num}_{i}_{fig.label}"
                    figure_url = save_page_image(file_hash, figure_img_name, crop_b64)

                    figures_data.append(
                        {
                            "image_url": figure_url,
                            "bbox": [p_xmin, p_ymin, p_xmax, p_ymax],
                            "explanation": "",
                            "page_num": page_num,
                            "label": fig.label,
                        }
                    )
                except Exception as e:
                    logger.warning(
                        f"[FigureService] AI Crop failed for item {i} on p.{page_num}: {e}"
                    )

        except Exception as e:
            logger.warning(f"[FigureService] AI Detection failed on p.{page_num}: {e}")
        """

        return figures_data
