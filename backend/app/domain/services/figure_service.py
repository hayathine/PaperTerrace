import base64
import io
from typing import Any

from app.providers.image_storage import save_page_image

# pdfplumber related imports for type hinting and functionality
from pdfplumber.display import PageImage
from pdfplumber.page import Page

from common.logger import logger
from common.schemas.bbox import BBoxModel
from common.utils.bbox import get_bbox_from_items, is_contained, scale_bbox

from .paddle_layout_service import get_layout_service


class FigureService:
    def __init__(self, ai_provider, model: str):
        self.ai_provider = ai_provider
        self.model = model
        self.layout_service = get_layout_service()

    async def detect_and_extract_figures(
        self,
        img_bytes: bytes,
        page_img: PageImage,
        page: Page,
        file_hash: str,
        page_num: int,
        zoom: float = 1.0,
        pdf_path: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Detect figures/tables/equations using ServiceB layout service and pdfplumber coordinates.
        """
        candidates = []

        # 0. Use ServiceB Layout Analysis if available (PRIORITY for CPU optimization)
        try:
            # ServiceBを使用した非同期レイアウト解析（画像データを直接送信）
            local_results = await self.layout_service.detect_layout_from_image_async(
                img_bytes
            )
            for res in local_results:
                # 結果の形式: {"bbox": {"x_min": ..., "y_min": ..., "x_max": ..., "y_max": ...}, "class_name": ..., "score": ...}
                class_name = res.get("class_name", "").lower()
                if class_name in ["figure", "table", "equation"]:
                    label = class_name
                    bbox_dict = res.get("bbox", {})
                    if bbox_dict:
                        bbox = get_bbox_from_items([bbox_dict])
                        # bbox format: [x1, y1, x2, y2]
                        bbox = scale_bbox(bbox, 1.0 / zoom, 1.0 / zoom)
                        candidates.append({"bbox": bbox, "label": label})
        except Exception as e:
            logger.warning(
                f"ServiceB layout analysis failed: {e}, falling back to pdfplumber only"
            )

        # 1. Add native pdfplumber images if not already covered by layout detector
        for img in page.images:
            bbox = get_bbox_from_items([img])
            # Check if this image area is already significantly covered by a candidate
            is_new = True
            for cand in candidates:
                if is_contained(bbox, cand["bbox"], threshold=0.8):
                    is_new = False
                    break

            if is_new:
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if 20 < w < page.width * 0.9 and 20 < h < page.height * 0.9:
                    candidates.append({"bbox": bbox, "label": "figure"})

        if not candidates:
            return []

        # 2. Process candidates, Extract and Save images
        final_areas = []
        # Sort candidates to process larger ones first (handle containment)
        candidates.sort(
            key=lambda x: (x["bbox"][2] - x["bbox"][0]) * (x["bbox"][3] - x["bbox"][1]),
            reverse=True,
        )

        for cand in candidates:
            bbox = cand["bbox"]
            margin = 5
            c_bbox = (
                max(0, bbox[0] - margin),
                max(0, bbox[1] - margin),
                min(page.width, bbox[2] + margin),
                min(page.height, bbox[3] + margin),
            )

            if any(
                is_contained(c_bbox, f["bbox_pt"], threshold=0.8) for f in final_areas
            ):
                continue

            try:
                # Use pre-rendered page_img instead of re-rendering with page.crop().to_image()
                # Calculate precise pixel coordinates based on actual image dimensions
                img_width, img_height = page_img.original.size
                scale_x = img_width / float(page.width)
                scale_y = img_height / float(page.height)

                # Map PDF points to pixel coordinates
                pixel_bbox = (
                    c_bbox[0] * scale_x,
                    c_bbox[1] * scale_y,
                    c_bbox[2] * scale_x,
                    c_bbox[3] * scale_y,
                )

                # Crop from the already rendered PIL image
                crop_pil = page_img.original.crop(pixel_bbox).convert("RGB")

                buffer = io.BytesIO()
                crop_pil.save(buffer, format="PNG")
                img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

                img_name = f"p{page_num}_{cand['label']}_{len(final_areas)}"
                url = save_page_image(file_hash, img_name, img_b64)

                final_areas.append(
                    {
                        "image_url": url,
                        "bbox": scale_bbox(c_bbox, zoom, zoom),
                        "bbox_pt": BBoxModel.from_list(c_bbox),
                        "explanation": "",
                        "page_num": page_num,
                        "label": cand["label"],
                    }
                )
            except Exception as e:
                logger.warning(
                    f"Extraction failed for {cand['label']} on p.{page_num}: {e}"
                )
                continue

        # Convert BBox objects to lists for the final response if they aren't serialized automatically
        return [
            {
                k: (v.to_list() if isinstance(v, BBoxModel) else v)
                for k, v in f.items()
                if k != "bbox_pt"
            }
            for f in final_areas
        ]
