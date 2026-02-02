import os
from typing import Any, Dict, List, Optional

from PIL import Image

from src.core.logger import logger
from src.infra.image_storage import save_page_image


class FigureService:
    def __init__(self, ai_provider, model: str):
        self.ai_provider = ai_provider
        self.model = model

    async def detect_and_extract_figures(
        self,
        img_bytes: bytes,
        page_image: Image.Image,
        file_hash: str,
        page_num: int,
        pdf_bytes: Optional[bytes] = None,
        page_height_pt: float = 792.0,
    ) -> List[Dict[str, Any]]:
        """
        Detect figures, tables, and equations.
        Figures: Extracted using pdfplumber coordinates (native images).
        Tables/Formulas: Detected using AI layout models (Heron/Surya/Gemini) as they are often more accurate for these structures.
        """
        if os.getenv("SKIP_FIGURE_EXTRACTION") == "True":
            logger.info(
                f"[FigureService] Skipping figure extraction for page {page_num} (SKIP_FIGURE_EXTRACTION=True)"
            )
            return []

        final_figures = []
        try:
            # 1. Get Figure coordinates from pdfplumber (native images)
            native_figures = []
            if pdf_bytes:
                from .native_figure_service import native_figure_service

                native_figures = native_figure_service.extract_figures(
                    pdf_bytes, page_num, page_image
                )

            # 2. Get Tables and Formulas from AI
            ai_items = await self._get_items(page_image, page_num)

            # Combine and deduplicate
            # Prioritize AI items (especially Heron) for tables/formulas
            all_items = ai_items.copy()
            for n_fig in native_figures:
                is_duplicate = False
                for a_item in ai_items:
                    if self._calculate_iou(n_fig["bbox"], a_item["bbox"]) > 0.5:
                        is_duplicate = True
                        break
                if not is_duplicate:
                    all_items.append(n_fig)

            # 3. Crop and save each item
            for i, item in enumerate(all_items):
                bbox = item["bbox"]
                fig_data = self._crop_and_save_pix_coords(
                    page_image, bbox, item["label"], page_num, i, file_hash
                )
                if fig_data:
                    final_figures.append(fig_data)

            # 4. Clear cache to free up memory (PIL images, etc.)
            from .cordinate_service import cordinate_service

            cordinate_service.clear_all_caches()

            return final_figures
        except Exception as e:
            logger.error(f"[FigureService] Figure extraction failed on p.{page_num}: {e}")
            return final_figures

    async def _get_items(self, page_image: Image.Image, page_num: int) -> List[Dict]:
        try:
            from .cordinate_service import cordinate_service

            # 一度の推論で全要素（Table, Formula, Figure等）を取得
            all_results = await cordinate_service.get_all_items(page_image)

            items = []
            target_labels = ("table", "formula")

            for res in all_results:
                label_lower = res.label.lower()
                # equation と formula は同一視
                if label_lower == "equation":
                    label_lower = "formula"

                if label_lower in target_labels:
                    items.append(
                        {
                            "bbox": res.bbox,
                            "label": res.label,
                            "confidence": res.confidence,
                        }
                    )
            return items
        except Exception as e:
            logger.error(f"[FigureService] items extraction failed: {e}")
            return []

    def _crop_and_save_pix_coords(self, page_image, bbox, label, page_num, idx, file_hash):
        """Crop using pixel-based coordinates."""
        import base64
        import io

        try:
            r_xmin, r_ymin, r_xmax, r_ymax = bbox
            # Clip to image bounds
            r_xmin = max(0, r_xmin)
            r_ymin = max(0, r_ymin)
            r_xmax = min(page_image.width, r_xmax)
            r_ymax = min(page_image.height, r_ymax)

            if (r_xmax - r_xmin) < 10 or (r_ymax - r_ymin) < 10:
                return None

            # Pillow crop is (left, top, right, bottom)
            crop_img = page_image.crop((int(r_xmin), int(r_ymin), int(r_xmax), int(r_ymax)))

            img_byte_arr = io.BytesIO()
            crop_img.save(img_byte_arr, format="PNG")
            crop_bytes = img_byte_arr.getvalue()

            # Save the image to storage
            img_name = f"p{page_num}_{label}_{idx}"
            url = save_page_image(file_hash, img_name, base64.b64encode(crop_bytes).decode("utf-8"))

            return {
                "image_url": url,
                "bbox": [r_xmin, r_ymin, r_xmax, r_ymax],
                "explanation": "",
                "page_num": page_num,
                "label": label,
            }
        except Exception as e:
            logger.warning(f"Crop failed: {e}")
            return None

    def _calculate_iou(self, box1, box2):
        """Intersection over Union."""
        ix0 = max(box1[0], box2[0])
        iy0 = max(box1[1], box2[1])
        ix1 = min(box1[2], box2[2])
        iy1 = min(box1[3], box2[3])

        if ix1 <= ix0 or iy1 <= iy0:
            return 0.0

        inter_area = (ix1 - ix0) * (iy1 - iy0)
        area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
        area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])

        return inter_area / float(area1 + area2 - inter_area)
