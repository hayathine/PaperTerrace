import base64
import io
from collections.abc import Sequence
from typing import Any

from app.logger import logger
from app.providers.image_storage import save_page_image

# pdfplumber related imports for type hinting and functionality
from pdfplumber.display import PageImage
from pdfplumber.page import Page

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
            if pdf_path:
                # ServiceBを使用した非同期レイアウト解析
                local_results = await self.layout_service.detect_layout_async(pdf_path, [page_num])
                for res in local_results:
                    if (
                        res.get("class") in ["figure", "table", "equation"]
                        and res.get("page") == page_num
                    ):
                        label = res["class"]
                        # Convert pixel coordinates to PDF points
                        bbox = res["bbox"]
                        if len(bbox) == 4:
                            # bbox format: [x1, y1, x2, y2]
                            bbox = [b / zoom for b in bbox]
                            candidates.append({"bbox": bbox, "label": label})
            else:
                # フォールバック: 従来の同期処理（非推奨）
                logger.warning(
                    "PDF path not provided, falling back to synchronous layout detection"
                )
                local_results = self.layout_service.detect_layout(img_bytes)
                for res in local_results:
                    if res["label"] in ["figure", "table", "equation", "chart"]:
                        label = res["label"] if res["label"] != "chart" else "figure"
                        # Convert pixel coordinates (at resolution) to PDF points
                        bbox = [b / zoom for b in res["bbox"]]
                        candidates.append({"bbox": bbox, "label": label})
        except Exception as e:
            logger.warning(f"ServiceB layout analysis failed: {e}, falling back to pdfplumber only")

        # 1. Add native pdfplumber images if not already covered by layout detector
        for img in page.images:
            bbox = [img["x0"], img["top"], img["x1"], img["bottom"]]
            if self._is_new_candidate(bbox, candidates):
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

            if not self._is_new_candidate(
                list(c_bbox), final_areas, key="bbox_pt", iou_threshold=0.8
            ):
                continue

            try:
                cropped = page.crop(c_bbox)
                crop_img = cropped.to_image(resolution=300)
                crop_pil = crop_img.original.convert("RGB")

                buffer = io.BytesIO()
                crop_pil.save(buffer, format="PNG")
                img_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

                img_name = f"p{page_num}_{cand['label']}_{len(final_areas)}"
                url = save_page_image(file_hash, img_name, img_b64)

                final_areas.append(
                    {
                        "image_url": url,
                        "bbox": [b * zoom for b in c_bbox],
                        "bbox_pt": list(c_bbox),
                        "explanation": "",
                        "page_num": page_num,
                        "label": cand["label"],
                    }
                )
            except Exception as e:
                logger.warning(f"Extraction failed for {cand['label']} on p.{page_num}: {e}")
                continue

        return [{k: v for k, v in f.items() if k != "bbox_pt"} for f in final_areas]

    def _is_new_candidate(
        self,
        bbox: Sequence[float],
        existing: list[dict],
        key: str = "bbox",
        iou_threshold: float = 0.8,
    ) -> bool:
        """Checks if a bbox is significantly new comparing to existing candidates."""
        for other in existing:
            o_bbox = other[key]
            ix0 = max(bbox[0], o_bbox[0])
            iy0 = max(bbox[1], o_bbox[1])
            ix1 = min(bbox[2], o_bbox[2])
            iy1 = min(bbox[3], o_bbox[3])

            if ix1 > ix0 and iy1 > iy0:
                inter_area = (ix1 - ix0) * (iy1 - iy0)
                cand_area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
                if inter_area / cand_area > iou_threshold:
                    return False
        return True

    def _cluster_objects(self, objs: list[dict], threshold: float = 10.0) -> list[list[float]]:
        """Simple clustering of objects based on proximity of their bboxes."""
        if not objs:
            return []

        bboxes = [(o["x0"], o["top"], o["x1"], o["bottom"]) for o in objs]
        clusters: list[list[float]] = []

        for bbox in bboxes:
            merged = False
            for i, cluster in enumerate(clusters):
                if not (
                    bbox[0] > cluster[2] + threshold
                    or bbox[2] < cluster[0] - threshold
                    or bbox[1] > cluster[3] + threshold
                    or bbox[3] < cluster[1] - threshold
                ):
                    clusters[i] = [
                        min(cluster[0], bbox[0]),
                        min(cluster[1], bbox[1]),
                        max(cluster[2], bbox[2]),
                        max(cluster[3], bbox[3]),
                    ]
                    merged = True
                    break
            if not merged:
                clusters.append(list(bbox))

        final_clusters: list[list[float]] = []
        for cluster in clusters:
            merged = False
            for i, f_cluster in enumerate(final_clusters):
                if not (
                    cluster[0] > f_cluster[2] + threshold
                    or cluster[2] < f_cluster[0] - threshold
                    or cluster[1] > f_cluster[3] + threshold
                    or cluster[3] < f_cluster[1] - threshold
                ):
                    final_clusters[i] = [
                        min(f_cluster[0], cluster[0]),
                        min(f_cluster[1], cluster[1]),
                        max(f_cluster[2], cluster[2]),
                        max(f_cluster[3], cluster[3]),
                    ]
                    merged = True
                    break
            if not merged:
                final_clusters.append(cluster)

        return final_clusters
