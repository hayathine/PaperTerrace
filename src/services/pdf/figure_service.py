import base64
import io
from typing import Any, Dict, List, Optional

# pdfplumber related imports for type hinting and functionality
from pdfplumber.display import PageImage
from pdfplumber.page import Page

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
        zoom: float = 1.0,
        pdf_path: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Detect figures/tables/equations using pdfplumber coordinates and extract them.
        """
        candidates = []
        page_area = page.width * page.height

        # 1. Native Images from pdfplumber
        for img in page.images:
            bbox = [img["x0"], img["top"], img["x1"], img["bottom"]]
            w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
            # Ignore small icons and full-page backgrounds (scans)
            if w < 20 or h < 20:
                continue
            if (w * h) > page_area * 0.85:
                continue
            candidates.append({"bbox": bbox, "label": "figure"})

        # 2. Tables from Camelot (if available) or pdfplumber
        has_camelot_tables = False
        if pdf_path:
            try:
                import camelot

                # Try lattice first (tables with lines)
                tables = camelot.read_pdf(pdf_path, pages=str(page_num), flavor="lattice")
                # If no tables found, try stream (tables with whitespace)
                if len(tables) == 0:
                    tables = camelot.read_pdf(pdf_path, pages=str(page_num), flavor="stream")

                if len(tables) > 0:
                    has_camelot_tables = True
                    for table in tables:
                        x1, y1, x2, y2 = table._bbox
                        # Camelot uses bottom-left origin, pdfplumber uses top-left origin
                        bbox = [x1, page.height - y2, x2, page.height - y1]
                        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                        if w > 40 and h > 20:
                            candidates.append({"bbox": bbox, "label": "table"})
            except Exception as e:
                logger.warning(f"Camelot table extraction failed on page {page_num}: {e}")

        if not has_camelot_tables:
            # Fallback to pdfplumber table detection
            strategies = [
                {"vertical_strategy": "lines", "horizontal_strategy": "lines"},
                {"vertical_strategy": "text", "horizontal_strategy": "lines"},
            ]
            for settings in strategies:
                try:
                    tables = page.find_tables(table_settings=settings)
                    for table in tables:
                        bbox = list(table.bbox)
                        w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                        if w > 40 and h > 20:
                            candidates.append({"bbox": bbox, "label": "table"})
                except Exception:
                    continue

        # 3. Equations and Vector Graphics (Clustering)
        # Identify characters with mathematical fonts
        math_chars = [
            c
            for c in page.chars
            if any(
                s in c.get("fontname", "").lower()
                for s in ["math", "symbol", "cmsy", "msam", "it-"]
            )
        ]

        # Groups lines, curves, and math chars into logical blocks (Equations/Plots)
        visual_objs = page.rects + page.curves + math_chars
        if visual_objs:
            clusters = self._cluster_objects(visual_objs, threshold=25.0)
            for cluster_bbox in clusters:
                w, h = cluster_bbox[2] - cluster_bbox[0], cluster_bbox[3] - cluster_bbox[1]
                if w < 30 or h < 10:
                    continue
                if (w * h) > page_area * 0.8:
                    continue
                label = "equation" if h < 60 and w > 100 else "figure"
                candidates.append({"bbox": cluster_bbox, "label": label})

        if not candidates:
            return []

        # 4. Merge and Deduplicate
        # Sort by area descending to handle containment
        candidates.sort(
            key=lambda x: (x["bbox"][2] - x["bbox"][0]) * (x["bbox"][3] - x["bbox"][1]),
            reverse=True,
        )
        final_areas = []

        for cand in candidates:
            bbox = cand["bbox"]
            margin = 5
            # Apply margin in PDF points
            # Ensure c_bbox is a tuple for page.crop()
            c_bbox = (
                max(0, bbox[0] - margin),
                max(0, bbox[1] - margin),
                min(page.width, bbox[2] + margin),
                min(page.height, bbox[3] + margin),
            )

            # Skip if this area is largely covered by a larger area already accepted
            is_redundant = False
            for accepted in final_areas:
                a_bbox = accepted["bbox_pt"]
                # Intersection
                ix0 = max(c_bbox[0], a_bbox[0])
                iy0 = max(c_bbox[1], a_bbox[1])
                ix1 = min(c_bbox[2], a_bbox[2])
                iy1 = min(c_bbox[3], a_bbox[3])

                if ix1 > ix0 and iy1 > iy0:
                    inter_area = (ix1 - ix0) * (iy1 - iy0)
                    cand_area = (c_bbox[2] - c_bbox[0]) * (c_bbox[3] - c_bbox[1])
                    if inter_area / cand_area > 0.8:
                        is_redundant = True
                        break

            if is_redundant:
                continue

            try:
                # Save crop
                cropped = page.crop(c_bbox)
                # Use high resolution for extraction
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
                        "bbox": [b * zoom for b in c_bbox],  # Convert to zoom pixels
                        "bbox_pt": c_bbox,  # Keep PDF points for redundancy check
                        "explanation": "",
                        "page_num": page_num,
                        "label": cand["label"],
                    }
                )
            except Exception:
                continue

        # Clean output
        return [{k: v for k, v in f.items() if k != "bbox_pt"} for f in final_areas]

    def _cluster_objects(self, objs: List[Dict], threshold: float = 10.0) -> List[List[float]]:
        """Simple clustering of objects based on proximity of their bboxes."""
        if not objs:
            return []

        bboxes = [(o["x0"], o["top"], o["x1"], o["bottom"]) for o in objs]
        clusters = []

        for bbox in bboxes:
            merged = False
            for i, cluster in enumerate(clusters):
                # Check if bbox is "close" to cluster (expand cluster by threshold)
                if not (
                    bbox[0] > cluster[2] + threshold
                    or bbox[2] < cluster[0] - threshold
                    or bbox[1] > cluster[3] + threshold
                    or bbox[3] < cluster[1] - threshold
                ):
                    # Merge
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

        # Second pass to merge overlapping clusters
        final_clusters = []
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
