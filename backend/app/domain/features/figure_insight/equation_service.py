import io
from typing import Any

import pdfplumber
from app.domain.prompts import CORE_SYSTEM_PROMPT, VISION_ANALYZE_EQUATION_PROMPT
from app.logger import logger
from app.providers import get_ai_provider
from app.schemas.gemini_schema import EquationAnalysisResponse


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

                for bbox in potential_bboxes:
                    # pdfplumber bbox is (x0, top, x1, bottom)
                    # Expand bbox slightly to catch symbols like exponents
                    expanded_bbox = (
                        max(0, bbox[0] - 5),
                        max(0, bbox[1] - 5),
                        min(page.width, bbox[2] + 5),
                        min(page.height, bbox[3] + 5),
                    )

                    # Crop and render for high-quality images
                    cropped_page = page.crop(expanded_bbox)
                    # Use high resolution for math clarity (400 DPI)
                    page_img = cropped_page.to_image(resolution=400)
                    img_pil = page_img.original.convert("RGB")

                    buffer = io.BytesIO()
                    img_pil.save(buffer, format="PNG")
                    img_bytes = buffer.getvalue()

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

        except Exception as e:
            logger.error(f"Equation extraction failed: {e}")

        return results

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
                                    self._get_bbox_from_chars(current_block)
                                )
                                current_block = [c]
                    if current_block:
                        potential_bboxes.append(
                            self._get_bbox_from_chars(current_block)
                        )

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
        except Exception as e:
            logger.error(f"Heuristic detection failed: {e}")
            return []

    def _get_bbox_from_chars(self, chars: list[dict]) -> list[float]:
        x0 = min(c["x0"] for c in chars)
        top = min(c["top"] for c in chars)
        x1 = max(c["x1"] for c in chars)
        bottom = max(c["bottom"] for c in chars)
        return [x0, top, x1, bottom]

    def _sanitize_bboxes(self, bboxes: list[list[float]]) -> list[list[float]]:
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
