import base64
import io
from typing import Any, Dict, List, Optional, Sequence

from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling_core.types.doc import DocItemLabel

# pdfplumber related imports for type hinting and functionality
from pdfplumber.display import PageImage
from pdfplumber.page import Page

from src.logger import logger
from src.providers.image_storage import save_page_image


class FigureService:
    def __init__(self, ai_provider, model: str):
        self.ai_provider = ai_provider
        self.model = model

        # Initialize Docling Converter
        pipeline_options = PdfPipelineOptions()
        pipeline_options.do_ocr = False
        pipeline_options.do_table_structure = True

        self.doc_converter = DocumentConverter(
            allowed_formats=[InputFormat.PDF],
            format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options)},
        )
        # Cache for converted documents: {file_hash: DoclingDocument}
        self._doc_cache: Dict[str, Any] = {}
        self._cache_order: List[str] = []

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
        Detect figures/tables/equations using Docling and pdfplumber coordinates.
        """
        candidates = []
        page_height = page.height

        # 1. Use Docling for structured items (Tables, Formulas, Pictures)
        if pdf_path:
            await self._add_docling_candidates(
                pdf_path, file_hash, page_num, page_height, candidates
            )

        # 2. Add native pdfplumber images if not already covered by Docling
        for img in page.images:
            bbox = [img["x0"], img["top"], img["x1"], img["bottom"]]
            if self._is_new_candidate(bbox, candidates):
                w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
                if 20 < w < page.width * 0.9 and 20 < h < page.height * 0.9:
                    candidates.append({"bbox": bbox, "label": "figure"})

        if not candidates:
            return []

        # 3. Process candidates, Extract and Save images
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

    async def _add_docling_candidates(
        self,
        pdf_path: str,
        file_hash: str,
        page_num: int,
        page_height: float,
        candidates: List[Dict],
    ):
        """Runs Docling (cached) and extracts candidates for the given page."""
        try:
            if file_hash not in self._doc_cache:
                logger.info(f"[FigureService] Converting PDF with Docling: {file_hash}")
                result = self.doc_converter.convert(pdf_path)

                # Manage cache size (Limit to 5 recent documents)
                if len(self._cache_order) >= 5:
                    old_hash = self._cache_order.pop(0)
                    self._doc_cache.pop(old_hash, None)

                self._doc_cache[file_hash] = result.document
                self._cache_order.append(file_hash)

            doc = self._doc_cache[file_hash]

            for item, level in doc.iterate_items():
                if not hasattr(item, "prov") or not item.prov:
                    continue

                for p in item.prov:
                    if p.page_no == page_num:
                        # Convert bbox to top-left origin
                        # Docling v2 BoundingBox has to_top_left_origin(page_height)
                        tl_bbox = p.bbox.to_top_left_origin(page_height)
                        bbox = [tl_bbox.l, tl_bbox.t, tl_bbox.r, tl_bbox.b]

                        label_val = (
                            item.label.value if hasattr(item.label, "value") else str(item.label)
                        )

                        if label_val in [
                            DocItemLabel.TABLE,
                            DocItemLabel.FORMULA,
                            DocItemLabel.PICTURE,
                            DocItemLabel.CHART,
                        ]:
                            our_label = "figure"
                            if label_val == DocItemLabel.TABLE:
                                our_label = "table"
                            elif label_val == DocItemLabel.FORMULA:
                                our_label = "equation"

                            candidates.append({"bbox": bbox, "label": our_label})

        except Exception as e:
            logger.error(f"[FigureService] Docling candidate extraction failed: {e}")

    def _is_new_candidate(
        self,
        bbox: Sequence[float],
        existing: List[Dict],
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

    def _cluster_objects(self, objs: List[Dict], threshold: float = 10.0) -> List[List[float]]:
        """Simple clustering of objects based on proximity of their bboxes."""
        if not objs:
            return []

        bboxes = [(o["x0"], o["top"], o["x1"], o["bottom"]) for o in objs]
        clusters: List[List[float]] = []

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

        final_clusters: List[List[float]] = []
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
