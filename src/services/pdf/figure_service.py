import base64
import io
from typing import Any, Dict, List

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
    ) -> List[Dict[str, Any]]:
        """
        Detect figures/tables/equations using pdfplumber coordinates and extract them.
        Since we no longer use layoutparser, we rely on pdfplumber's object detection.
        """
        figures_data = []

        # 1. Extract Native Images from pdfplumber
        # pdfplumber provides coordinates for each image object in the PDF
        logger.debug(f"[FigureService] p.{page_num}: Checking pdfplumber images")
        for i, img_obj in enumerate(page.images):
            try:
                # bbox is (x0, top, x1, bottom) in PDF points
                bbox = (img_obj["x0"], img_obj["top"], img_obj["x1"], img_obj["bottom"])

                # Filtering very small icons/noise
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                if width < 20 or height < 20:  # Icons are often tiny
                    continue

                # Crop the region from the page
                # We use page.crop to get the vector/image content of that area
                # then convert to image for extraction
                margin = 2
                c_bbox = (
                    max(0, bbox[0] - margin),
                    max(0, bbox[1] - margin),
                    min(page.width, bbox[2] + margin),
                    min(page.height, bbox[3] + margin),
                )

                cropped = page.crop(c_bbox)
                # Render at high resolution
                crop_img = cropped.to_image(resolution=300)
                crop_pil = crop_img.original.convert("RGB")

                buffer = io.BytesIO()
                crop_pil.save(buffer, format="PNG")
                png_bytes = buffer.getvalue()

                img_b64 = base64.b64encode(png_bytes).decode("utf-8")
                figure_img_name = f"plumber_img_{page_num}_{i}"

                figure_url = save_page_image(file_hash, figure_img_name, img_b64)

                figures_data.append(
                    {
                        "image_url": figure_url,
                        "bbox": [
                            c_bbox[0] * zoom,
                            c_bbox[1] * zoom,
                            c_bbox[2] * zoom,
                            c_bbox[3] * zoom,
                        ],
                        "explanation": "",
                        "page_num": page_num,
                        "label": "figure",
                    }
                )
            except Exception as e:
                logger.warning(f"[FigureService] p.{page_num}: Image {i} extraction failed: {e}")

        # 2. Extract Tables using pdfplumber
        logger.debug(f"[FigureService] p.{page_num}: Attempting table detection")
        try:
            tables = page.find_tables()
            for i, table in enumerate(tables):
                bbox = table.bbox
                width = bbox[2] - bbox[0]
                height = bbox[3] - bbox[1]
                if width < 50 or height < 30:
                    continue

                # Avoid duplicates if already covered by an image (some tables are images)
                is_duplicate = False
                for fig in figures_data:
                    fb = fig["bbox"]
                    # If center of table is within a figure, skip
                    cx, cy = (bbox[0] + bbox[2]) / 2 * zoom, (bbox[1] + bbox[3]) / 2 * zoom
                    if fb[0] < cx < fb[2] and fb[1] < cy < fb[3]:
                        is_duplicate = True
                        break
                if is_duplicate:
                    continue

                margin = 5
                c_bbox = (
                    max(0, bbox[0] - margin),
                    max(0, bbox[1] - margin),
                    min(page.width, bbox[2] + margin),
                    min(page.height, bbox[3] + margin),
                )

                cropped = page.crop(c_bbox)
                crop_img = cropped.to_image(resolution=300)
                crop_pil = crop_img.original.convert("RGB")

                buffer = io.BytesIO()
                crop_pil.save(buffer, format="PNG")
                crop_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

                table_img_name = f"plumber_table_{page_num}_{i}"
                table_url = save_page_image(file_hash, table_img_name, crop_b64)

                figures_data.append(
                    {
                        "image_url": table_url,
                        "bbox": [
                            c_bbox[0] * zoom,
                            c_bbox[1] * zoom,
                            c_bbox[2] * zoom,
                            c_bbox[3] * zoom,
                        ],
                        "explanation": "",
                        "page_num": page_num,
                        "label": "table",
                    }
                )
        except Exception as e:
            logger.warning(f"[FigureService] p.{page_num}: Table detection failed: {e}")

        # 3. Detect Equations/Vector clusters
        # Equations often appear as clusters of 'rects' or 'curves' without much text
        logger.debug(f"[FigureService] p.{page_num}: Checking for vector graphics clusters")
        try:
            # Get all non-text visual objects
            visual_objs = page.rects + page.curves
            if visual_objs:
                # Group objects that are very close to each other
                clusters = self._cluster_objects(visual_objs)
                for i, cluster_bbox in enumerate(clusters):
                    width = cluster_bbox[2] - cluster_bbox[0]
                    height = cluster_bbox[3] - cluster_bbox[1]

                    # Filtering noise: too small or too thin
                    if width < 30 or height < 10:
                        continue
                    # Filtering background: too large
                    if width > page.width * 0.9 and height > page.height * 0.9:
                        continue

                    # Overlap check with existing figures/tables
                    is_duplicate = False
                    for fig in figures_data:
                        fb = fig["bbox"]
                        # Point in cluster check (center of cluster)
                        cx, cy = (
                            (cluster_bbox[0] + cluster_bbox[2]) / 2 * zoom,
                            (cluster_bbox[1] + cluster_bbox[3]) / 2 * zoom,
                        )
                        if fb[0] < cx < fb[2] and fb[1] < cy < fb[3]:
                            is_duplicate = True
                            break
                    if is_duplicate:
                        continue

                    # Crop and save
                    margin = 5
                    c_bbox = (
                        max(0, cluster_bbox[0] - margin),
                        max(0, cluster_bbox[1] - margin),
                        min(page.width, cluster_bbox[2] + margin),
                        min(page.height, cluster_bbox[3] + margin),
                    )

                    try:
                        cropped = page.crop(c_bbox)
                        crop_img = cropped.to_image(resolution=300)
                        crop_pil = crop_img.original.convert("RGB")

                        buffer = io.BytesIO()
                        crop_pil.save(buffer, format="PNG")
                        crop_b64 = base64.b64encode(buffer.getvalue()).decode("utf-8")

                        vector_img_name = f"plumber_vector_{page_num}_{i}"
                        vector_url = save_page_image(file_hash, vector_img_name, crop_b64)

                        figures_data.append(
                            {
                                "image_url": vector_url,
                                "bbox": [
                                    c_bbox[0] * zoom,
                                    c_bbox[1] * zoom,
                                    c_bbox[2] * zoom,
                                    c_bbox[3] * zoom,
                                ],
                                "explanation": "",
                                "page_num": page_num,
                                "label": "visual",  # General label
                            }
                        )
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"[FigureService] p.{page_num}: Vector clustering failed: {e}")

        return figures_data

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
