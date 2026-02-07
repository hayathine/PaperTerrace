import io
from typing import Any

import pdfplumber
from app.domain.prompts import CORE_SYSTEM_PROMPT, VISION_ANALYZE_EQUATION_PROMPT
from app.providers import get_ai_provider
from app.schemas.gemini_schema import EquationAnalysisResponse

from common.logger import logger
from common.schemas.bbox import BBoxModel
from common.utils.bbox import get_bbox_from_items, sanitize_bboxes


class EquationService:
    """Service to detect and convert mathematical equations to LaTeX."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.model = "gemini-2.0-flash"  # Use a capable vision model

    async def detect_and_convert_equations(
        self, file_bytes: bytes, page_num: int, target_lang: str = "ja"
    ) -> list[dict[str, Any]]:
        """
        1. Identify potential equation areas using pdfplumber heuristics.
        2. Crop and analyze these areas using AI.
        3. Convert to LaTeX and return results.
        """
        potential_bboxes = self._identify_potential_equation_areas(file_bytes, page_num)
        if not potential_bboxes:
            return []

        results = []
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                if page_num > len(pdf.pages):
                    return []
                page = pdf.pages[page_num - 1]

                # Render the entire page once to reuse for multiple crops
                # High resolution is needed for math clarity
                full_page_img = page.to_image(resolution=200)
                full_img_pil = full_page_img.original

                # Calculate precise pixel coordinates based on actual image dimensions
                img_width, img_height = full_img_pil.size
                scale_x = img_width / float(page.width)
                scale_y = img_height / float(page.height)

                for bbox in potential_bboxes:
                    # pdfplumber bbox is (x0, top, x1, bottom)
                    # Expand bbox slightly to catch symbols like exponents
                    expanded_bbox = (
                        max(0, bbox[0] - 5),
                        max(0, bbox[1] - 5),
                        min(page.width, bbox[2] + 5),
                        min(page.height, bbox[3] + 5),
                    )

                    # Map PDF points to pixel coordinates
                    pixel_bbox = (
                        expanded_bbox[0] * scale_x,
                        expanded_bbox[1] * scale_y,
                        expanded_bbox[2] * scale_x,
                        expanded_bbox[3] * scale_y,
                    )

                    # Crop from the already rendered PIL image
                    img_pil = full_img_pil.crop(pixel_bbox).convert("RGB")

                    buffer = io.BytesIO()
                    img_pil.save(buffer, format="PNG")
                    img_bytes = buffer.getvalue()

                    # Analyze with AI
                    analysis = await self._analyze_bbox_with_ai(img_bytes, target_lang)
                    if analysis and analysis.is_equation and analysis.confidence > 0.6:
                        results.append(
                            {
                                "bbox": BBoxModel.from_list(bbox),
                                "latex": analysis.latex,
                                "explanation": analysis.explanation,
                                "page_num": page_num,
                            }
                        )

        except Exception as e:
            logger.error(f"Equation extraction failed: {e}")

        return [
            {k: (v.to_list() if isinstance(v, BBoxModel) else v) for k, v in r.items()}
            for r in results
        ]

    def _identify_potential_equation_areas(
        self, file_bytes: bytes, page_num: int
    ) -> list[list[float]]:
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
                                potential_bboxes.append(
                                    get_bbox_from_items(current_block)
                                )
                                current_block = [c]
                    if current_block:
                        potential_bboxes.append(get_bbox_from_items(current_block))

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
                return sanitize_bboxes(potential_bboxes)
        except Exception as e:
            logger.error(f"Heuristic detection failed: {e}")
            return []

    async def _analyze_bbox_with_ai(
        self, img_bytes: bytes, target_lang: str
    ) -> EquationAnalysisResponse | None:
        from ..translate import SUPPORTED_LANGUAGES

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)

        prompt = VISION_ANALYZE_EQUATION_PROMPT.format(lang_name=lang_name)

        try:
            response = await self.ai_provider.generate_with_image(
                prompt,
                img_bytes,
                "image/png",
                response_model=EquationAnalysisResponse,
                system_instruction=CORE_SYSTEM_PROMPT,
            )
            return response
        except Exception as e:
            logger.warning(f"AI Equation analysis failed: {e}")
            return None
