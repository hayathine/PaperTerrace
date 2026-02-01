import io
from typing import Any, Dict, List, Optional

import pdfplumber
from pydantic import BaseModel

from src.core.logger import logger
from src.domain.prompts import CORE_SYSTEM_PROMPT, VISION_ANALYZE_EQUATION_PROMPT
from src.infra import get_ai_provider


class EquationAnalysisResponse(BaseModel):
    is_equation: bool
    confidence: float
    latex: str
    explanation: str


class EquationService:
    """Service to detect and convert mathematical equations to LaTeX."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = "gemini-2.0-flash"  # Use a capable vision model

    async def detect_and_convert_equations(
        self, file_bytes: bytes, page_num: int, target_lang: str = "ja"
    ) -> List[Dict[str, Any]]:
        """
        Detect and convert mathematical equations using Docling for structure
        and AI for verification/explanation.
        """
        import time

        results = []
        try:
            start_t = time.time()

            # 1. Detect equations using Surya (primary)
            surya_bboxes = []
            try:
                with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                    if page_num <= len(pdf.pages):
                        page = pdf.pages[page_num - 1]
                        dpi = 300  # Use 300 DPI for detection (good balance of speed/accuracy)
                        im = page.to_image(resolution=dpi).original

                        from src.domain.services.pdf.surya_service import surya_service

                        surya_results = await surya_service.detect_layout(im)

                        for res in surya_results:
                            if res["label"] == "Formula":
                                # Convert pixel coords back to pdfplumber points
                                # points = pixels * (72 / dpi)
                                px_bbox = res["bbox"]
                                pt_bbox = [
                                    px_bbox[0] * (72 / dpi),
                                    px_bbox[1] * (72 / dpi),
                                    px_bbox[2] * (72 / dpi),
                                    px_bbox[3] * (72 / dpi),
                                ]
                                surya_bboxes.append(pt_bbox)

                        logger.info(
                            f"[Equations] Surya found {len(surya_bboxes)} candidates in {time.time() - start_t:.2f}s"
                        )
            except Exception as e:
                logger.error(f"[Equations] Surya detection failed: {e}")

            if not surya_bboxes:
                # Fallback to heuristics if surya found nothing
                logger.info("[Equations] Falling back to heuristic detection")
                potential_bboxes = self._identify_potential_equation_areas(file_bytes, page_num)
            else:
                potential_bboxes = surya_bboxes

            if not potential_bboxes:
                return []

            # Reuse AI analysis for explanation and verification
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if page_num > len(pdf.pages):
                    return []
                page = pdf.pages[page_num - 1]

                for i, bbox in enumerate(potential_bboxes):
                    try:
                        # Expand bbox slightly for better image
                        expanded_bbox = (
                            max(0, bbox[0] - 5),
                            max(0, bbox[1] - 5),
                            min(page.width, bbox[2] + 5),
                            min(page.height, bbox[3] + 5),
                        )

                        page_crop = page.crop(expanded_bbox)
                        im_crop = page_crop.to_image(resolution=288)

                        img_byte_arr = io.BytesIO()
                        im_crop.original.save(img_byte_arr, format="PNG")
                        img_bytes = img_byte_arr.getvalue()

                        # Analyze with AI
                        analysis = await self._analyze_bbox_with_ai(img_bytes, target_lang)
                        if analysis and analysis.is_equation and analysis.confidence > 0.6:
                            results.append(
                                {
                                    "bbox": bbox,
                                    "latex": analysis.latex,
                                    "explanation": analysis.explanation,
                                    "page_num": page_num,
                                }
                            )
                            logger.debug(f"[Equations] Verified equation {i + 1} on p.{page_num}")
                    except Exception as cand_err:
                        logger.error(f"[Equations] Candidate error: {cand_err}")
                        continue

            logger.info(f"[Equations] Finished page {page_num}, found {len(results)} equations")
        except Exception:
            logger.exception("[Equations] Extraction failed")

        return results

    def _identify_potential_equation_areas(
        self, file_bytes: bytes, page_num: int
    ) -> List[List[float]]:
        """
        Heuristic detection using pdfplumber:
        - Identify large vertical gaps between text lines.
        - Identify characters with math fonts.
        """
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if page_num > len(pdf.pages):
                    return []
                page = pdf.pages[page_num - 1]

                # 1. Look for mathematical fonts
                chars = page.chars
                math_chars = [
                    c
                    for c in chars
                    if any(
                        s in c["fontname"].lower()
                        for s in ["math", "symbol", "cmsy", "msam", "it-"]
                    )
                ]

                potential_bboxes = []

                # Group math characters into blocks
                if math_chars:
                    # Simple clustering: if chars are close vertically, group them
                    math_chars.sort(key=lambda x: x["top"])
                    current_block = []
                    for c in math_chars:
                        if not current_block:
                            current_block.append(c)
                        else:
                            last_char = current_block[-1]
                            if c["top"] - last_char["bottom"] < 10:  # Close enough
                                current_block.append(c)
                            else:
                                # Close current block and start new
                                potential_bboxes.append(self._get_bbox_from_chars(current_block))
                                current_block = [c]
                    if current_block:
                        potential_bboxes.append(self._get_bbox_from_chars(current_block))

                # 2. Look for large gaps (whitespace analysis)
                # Group text into lines
                text_objects = page.extract_words()
                if len(text_objects) > 1:
                    text_objects.sort(key=lambda x: x["top"])
                    for i in range(len(text_objects) - 1):
                        gap = text_objects[i + 1]["top"] - text_objects[i]["bottom"]
                        if 15 < gap < 100:  # Threshold for potential equation gap
                            # Check if this area contains non-text objects (drawings, etc.)
                            area_bbox = (
                                0,
                                text_objects[i]["bottom"],
                                page.width,
                                text_objects[i + 1]["top"],
                            )
                            # Add this region as a candidate
                            potential_bboxes.append(
                                [area_bbox[0], area_bbox[1], area_bbox[2], area_bbox[3]]
                            )

                # Filter and deduplicate bboxes
                return self._sanitize_bboxes(potential_bboxes)
        except Exception:
            logger.exception(f"[Equations] Heuristic detection failed on page {page_num}")
            return []

    def _get_bbox_from_chars(self, chars: List[Dict]) -> List[float]:
        x0 = min(c["x0"] for c in chars)
        top = min(c["top"] for c in chars)
        x1 = max(c["x1"] for c in chars)
        bottom = max(c["bottom"] for c in chars)
        return [x0, top, x1, bottom]

    def _sanitize_bboxes(self, bboxes: List[List[float]]) -> List[List[float]]:
        # Remove overlaps and small bboxes
        if not bboxes:
            return []

        # Merge overlapping or very close bboxes
        bboxes.sort(key=lambda x: x[1])
        merged = []
        if bboxes:
            curr = bboxes[0]
            for next_bbox in bboxes[1:]:
                # If they overlap vertically significantly
                if next_bbox[1] < curr[3] + 5:
                    curr[0] = min(curr[0], next_bbox[0])
                    curr[1] = min(curr[1], next_bbox[1])
                    curr[2] = max(curr[2], next_bbox[2])
                    curr[3] = max(curr[3], next_bbox[3])
                else:
                    merged.append(curr)
                    curr = next_bbox
            merged.append(curr)

        return [b for b in merged if (b[2] - b[0]) > 5 and (b[3] - b[1]) > 5]

    async def _analyze_bbox_with_ai(
        self, img_bytes: bytes, target_lang: str
    ) -> Optional[EquationAnalysisResponse]:
        from ..translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        prompt = VISION_ANALYZE_EQUATION_PROMPT.format(lang_name=lang_name)
        instruction = CORE_SYSTEM_PROMPT.format(lang_name=lang_name)

        try:
            response = await self.ai_provider.generate_with_image(
                prompt,
                img_bytes,
                "image/png",
                response_model=EquationAnalysisResponse,
                system_instruction=instruction,
            )
            return response
        except Exception as e:
            logger.warning(f"[Equations] AI analysis failed: {e}")
            return None
