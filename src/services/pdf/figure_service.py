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
        Detect figures/tables and extract them as separate images.
        """
        figures_data = []

        # 1. Native extraction (using pypdf with size/aspect ratio filtering)
        if pypdf_page and hasattr(pypdf_page, "images"):
            logger.debug(f"[FigureService] p.{page_num}: Checking native images")
            try:
                found_count = 0
                for i, image_file in enumerate(pypdf_page.images):
                    img_data = image_file.data
                    if len(img_data) < 1000:
                        continue

                    try:
                        with Image.open(io.BytesIO(img_data)) as img:
                            width, height = img.size
                    except Exception:
                        continue

                    # Filtering small/weird images (noise reduction)
                    if width < 100 or height < 100:
                        continue
                    if height > 0 and width / height > 5:
                        continue
                    if page_num == 1 and width < 300:  # Banner on first page
                        continue

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
                        f"[FigureService] p.{page_num}: Extracted {found_count} native images"
                    )
            except Exception as e:
                logger.warning(f"[FigureService] p.{page_num}: Native extraction failed: {e}")

        # 2. Table detection using pdfplumber (for text-based tables)
        logger.debug(f"[FigureService] p.{page_num}: Attempting table detection")
        try:
            tables = page.find_tables()
            if tables:
                logger.info(f"[FigureService] p.{page_num}: Found {len(tables)} tables")
                for i, table in enumerate(tables):
                    bbox = table.bbox  # (x0, top, x1, bottom)

                    # Expand bbox slightly
                    margin = 5
                    p_xmin = max(0, bbox[0] - margin)
                    p_ymin = max(0, bbox[1] - margin)
                    p_xmax = min(page.width, bbox[2] + margin)
                    p_ymax = min(page.height, bbox[3] + margin)

                    cropped_page = page.crop((p_xmin, p_ymin, p_xmax, p_ymax))
                    crop_img_obj = cropped_page.to_image(resolution=300)
                    crop_pil = crop_img_obj.original

                    buffer = io.BytesIO()
                    crop_pil.save(buffer, format="PNG")
                    crop_bytes = buffer.getvalue()

                    crop_b64 = base64.b64encode(crop_bytes).decode("utf-8")
                    table_img_name = f"table_{page_num}_{i}"
                    table_url = save_page_image(file_hash, table_img_name, crop_b64)

                    figures_data.append(
                        {
                            "image_url": table_url,
                            "bbox": [p_xmin, p_ymin, p_xmax, p_ymax],
                            "explanation": "",
                            "page_num": page_num,
                            "label": "table",
                        }
                    )
        except Exception as e:
            logger.warning(f"[FigureService] p.{page_num}: Table detection failed: {e}")

        return figures_data
