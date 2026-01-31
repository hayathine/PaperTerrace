import base64
import io
from typing import Any, Dict, List, Optional

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
        layout_blocks: Optional[List[Dict[str, Any]]] = None,
        zoom: float = 1.0,
    ) -> List[Dict[str, Any]]:
        """
        Detect figures/tables and extract them as separate images.
        """
        figures_data = []

        # 1. Native extraction (using pypdf with size/aspect ratio filtering)
        if pypdf_page and hasattr(pypdf_page, "images"):
            logger.debug(f"[FigureService] p.{page_num}: Checking native images")
            found_count = 0
            for i, image_file in enumerate(pypdf_page.images):
                try:
                    img_data = image_file.data
                    # Use PIL to normalize to PNG and check size
                    try:
                        with Image.open(io.BytesIO(img_data)) as img:
                            width, height = img.size

                            # Filtering icons and small noise
                            if width < 150 or height < 150:
                                continue
                            if height > 0 and width / height > 5:
                                continue

                            # Normalize to PNG to ensure browser compatibility
                            # Some PDF images are in CMYK or exotic formats (JPX)
                            img = img.convert("RGB")
                            buffer = io.BytesIO()
                            img.save(buffer, format="PNG")
                            png_bytes = buffer.getvalue()

                            if len(png_bytes) < 2000:
                                continue

                            img_b64 = base64.b64encode(png_bytes).decode("utf-8")
                    except Exception as e:
                        logger.warning(
                            f"[FigureService] p.{page_num}: PIL processing failed for native image {i}: {e}"
                        )
                        continue

                    # Sanitize name to avoid directory escape or invalid paths
                    safe_name = "".join([c if c.isalnum() else "_" for c in image_file.name])
                    figure_img_name = f"native_img_{page_num}_{i}_{safe_name}"

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
                except Exception as e:
                    logger.warning(f"[FigureService] p.{page_num}: Native image {i} failed: {e}")
                    continue

            if found_count > 0:
                logger.info(f"[FigureService] p.{page_num}: Extracted {found_count} native images")

        # 2. Table detection using pdfplumber (for text-based tables)
        logger.debug(f"[FigureService] p.{page_num}: Attempting table detection")
        try:
            tables = page.find_tables()
            if tables:
                logger.debug(f"[FigureService] p.{page_num}: Found {len(tables)} potential tables")
                for i, table in enumerate(tables):
                    bbox = table.bbox  # (x0, top, x1, bottom)

                    # Filtering very small tables/lines (likely icons or structural noise)
                    width = bbox[2] - bbox[0]
                    height = bbox[3] - bbox[1]
                    if width < 120 or height < 60:
                        continue

                    # Expand bbox slightly
                    margin = 5
                    p_xmin = max(0, bbox[0] - margin)
                    p_ymin = max(0, bbox[1] - margin)
                    p_xmax = min(page.width, bbox[2] + margin)
                    p_ymax = min(page.height, bbox[3] + margin)

                    cropped_page = page.crop((p_xmin, p_ymin, p_xmax, p_ymax))
                    crop_img_obj = cropped_page.to_image(resolution=300)
                    crop_pil = crop_img_obj.original.convert("RGB")

                    buffer = io.BytesIO()
                    crop_pil.save(buffer, format="PNG")
                    crop_bytes = buffer.getvalue()

                    crop_b64 = base64.b64encode(crop_bytes).decode("utf-8")
                    table_img_name = f"table_{page_num}_{i}"
                    table_url = save_page_image(file_hash, table_img_name, crop_b64)

                    figures_data.append(
                        {
                            "image_url": table_url,
                            "bbox": [p_xmin * zoom, p_ymin * zoom, p_xmax * zoom, p_ymax * zoom],
                            "explanation": "",
                            "page_num": page_num,
                            "label": "table",
                        }
                    )
        except Exception as e:
            logger.warning(f"[FigureService] p.{page_num}: Table detection failed: {e}")

        # 3. LayoutParser blocks extraction (High Quality)
        if layout_blocks:
            logger.debug(
                f"[FigureService] p.{page_num}: Processing {len(layout_blocks)} layout blocks"
            )
            for i, block in enumerate(layout_blocks):
                # Filter for useful types (Figure, Table, and potentially Equation)
                # PubLayNet types: Text, Title, List, Table, Figure
                if block["type"] not in ["Figure", "Table"]:
                    continue

                bbox_px = block["bbox"]  # [x1, y1, x2, y2] in pixels

                # Convert to PDF points for cropping
                p_xmin = bbox_px[0] / zoom
                p_ymin = bbox_px[1] / zoom
                p_xmax = bbox_px[2] / zoom
                p_ymax = bbox_px[3] / zoom

                # Check for duplicates or overlapping areas
                is_overlap = False
                for existing in figures_data:
                    eb = existing["bbox"]
                    if eb[0] == 0:
                        continue  # Skip native images with no bbox

                    # Convert eb back to center for check (eb is in pixels now)
                    ecenter_x = (eb[0] + eb[2]) / 2
                    ecenter_y = (eb[1] + eb[3]) / 2
                    if bbox_px[0] < ecenter_x < bbox_px[2] and bbox_px[1] < ecenter_y < bbox_px[3]:
                        is_overlap = True
                        break

                if is_overlap:
                    continue

                try:
                    # Crop and save
                    cropped_page = page.crop((p_xmin, p_ymin, p_xmax, p_ymax))
                    crop_img_obj = cropped_page.to_image(resolution=300)
                    crop_pil = crop_img_obj.original.convert("RGB")

                    buffer = io.BytesIO()
                    crop_pil.save(buffer, format="PNG")
                    crop_bytes = buffer.getvalue()

                    crop_b64 = base64.b64encode(crop_bytes).decode("utf-8")
                    block_img_name = f"layout_{block['type'].lower()}_{page_num}_{i}"
                    block_url = save_page_image(file_hash, block_img_name, crop_b64)

                    figures_data.append(
                        {
                            "image_url": block_url,
                            "bbox": [bbox_px[0], bbox_px[1], bbox_px[2], bbox_px[3]],
                            "explanation": "",
                            "page_num": page_num,
                            "label": block["type"].lower(),
                        }
                    )
                except Exception as e:
                    logger.warning(f"[FigureService] p.{page_num}: Block extraction failed: {e}")

        return figures_data
