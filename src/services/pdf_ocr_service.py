import base64
import io
import json
from typing import AsyncGenerator, Optional

import pdfplumber

from src.crud import get_ocr_from_db, save_ocr_to_db
from src.logger import logger
from src.providers import get_ai_provider
from src.providers.image_storage import get_page_images, save_page_image
from src.utils import _get_file_hash

from .pdf.abstract_service import AbstractService
from .pdf.figure_service import FigureService
from .pdf.language_service import LanguageService


class PDFOCRService:
    def __init__(self, model):
        self.ai_provider = get_ai_provider()
        self.model = model
        self.figure_service = FigureService(self.ai_provider, self.model)
        self.language_service = LanguageService(self.ai_provider, self.model)

    def extract_abstract_text(self, file_bytes: bytes) -> Optional[str]:
        """Extract abstract using specialized service."""
        return AbstractService.extract_abstract(file_bytes)

    async def detect_language_from_pdf(self, file_bytes: bytes) -> str:
        """Detect language using specialized service."""
        return await self.language_service.detect_language(file_bytes)

    async def extract_text_streaming(
        self, file_bytes: bytes, filename: str = "unknown.pdf", user_plan: str = "free"
    ) -> AsyncGenerator:
        """Processes PDF pages one by one and streams results."""
        file_hash = _get_file_hash(file_bytes)

        # 1. Cache handling
        cached_result = await self._handle_cache(file_hash)
        if cached_result:
            for page in cached_result:
                yield page
            return

        logger.info(f"--- AI OCR Streaming: {filename} ---")

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                total_pages = len(pdf.pages)
                all_text_parts = []
                all_layout_parts = []

                for page_num in range(total_pages):
                    logger.debug(f"[OCR] Starting processing page {page_num + 1}/{total_pages}")

                    async for result in self._process_page_incremental(
                        pdf.pages[page_num], page_num, total_pages, file_hash
                    ):
                        # result is (page_num+1, total_pages, page_text, is_last, file_hash, img_url, layout_data)
                        if result[2] is not None:  # Final result per page
                            page_text = result[2]
                            layout_data = result[6]
                            all_text_parts.append(page_text)
                            all_layout_parts.append(layout_data)
                        yield result

            # 2. Finalize and save to DB
            self._finalize_ocr(file_hash, filename, all_text_parts, all_layout_parts)

        except Exception as e:
            logger.error(f"OCR streaming failed: {e}")
            yield (0, 0, f"ERROR_API_FAILED: {str(e)}", True, file_hash, None, None)

    async def _handle_cache(self, file_hash: str) -> Optional[list]:
        """Check if OCR is cached and return formatted pages if so."""
        logger.debug(f"[OCR] Checking cache for hash: {file_hash}")
        cache_data = get_ocr_from_db(file_hash)
        if not cache_data:
            logger.info(f"[OCR] Cache miss for hash: {file_hash}")
            return None

        logger.info(f"[OCR] Cache hit for hash: {file_hash}")
        ocr_text = cache_data["ocr_text"]
        layout_json = cache_data.get("layout_json")
        layout_data_list = []
        if layout_json:
            try:
                layout_data_list = json.loads(layout_json)
            except Exception:
                logger.warning(f"Failed to parse layout_json from cache for {file_hash}")

        # Basic split by separator
        pages_text = ocr_text.split("\n\n---\n\n")
        cached_images = get_page_images(file_hash)

        pages = []
        for i, img_url in enumerate(cached_images):
            text = pages_text[i] if i < len(pages_text) else ""
            layout = layout_data_list[i] if i < len(layout_data_list) else None
            pages.append(
                (
                    i + 1,
                    len(cached_images),
                    text,
                    False,  # is_last - this is not known from cache, but not critical for display
                    file_hash,
                    img_url,
                    layout,
                )
            )
        return pages

    async def _process_page_incremental(self, page, page_idx, total_pages, file_hash):
        """Process a single page: render image, OCR, detect layout/figures."""
        page_num = page_idx + 1

        # 1. Render image (FAST)
        resolution = 300  # Standard high-quality DPI
        zoom = resolution / 72.0
        page_img = page.to_image(resolution=resolution, antialias=True)
        img_pil = page_img.original.convert("RGB")

        buffer = io.BytesIO()
        img_pil.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()

        page_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
        image_url = save_page_image(file_hash, page_num, page_image_b64)

        is_last = page_idx == total_pages - 1

        # Yield PHASE 1: Image Ready
        logger.debug(f"[OCR] Page {page_num}: Image ready, yielding partial result")
        yield (page_num, total_pages, None, is_last, file_hash, image_url, None)

        # 2. Extract Text (SLOW)
        page_text, layout_data = await self._extract_native_or_vision_text(
            page, img_bytes, img_pil, zoom
        )
        if not layout_data:
            layout_data = {"width": img_pil.width, "height": img_pil.height, "words": []}

        # 3. Figure extraction (SLOW)
        figures = await self.figure_service.detect_and_extract_figures(
            img_bytes,
            page_img,
            page,
            file_hash,
            page_num,
            zoom=zoom,
        )
        if figures:
            logger.info(f"[OCR] Page {page_num}: Detected {len(figures)} figures/images")
            if "figures" not in layout_data:
                layout_data["figures"] = []
            layout_data["figures"].extend(figures)
        else:
            logger.debug(f"[OCR] Page {page_num}: No figures detected")

        # Yield PHASE 2: Full analysis complete
        logger.debug(f"[OCR] Page {page_num}: Full analysis complete")
        yield (page_num, total_pages, page_text, is_last, file_hash, image_url, layout_data)

    async def _extract_native_or_vision_text(self, page, img_bytes, img_pil, zoom):
        """Try to extract text from PDF directly, fallback to Vision API or Gemini."""
        page_num = page.page_number
        logger.debug(f"[OCR] p.{page_num}: Attempting native word extraction")

        words = page.extract_words(use_text_flow=True, x_tolerance=1, y_tolerance=3)
        if words:
            logger.info(
                f"[OCR] p.{page_num}: Native word extraction successful ({len(words)} words)"
            )
            word_list = [
                {
                    "word": w["text"],
                    "bbox": [w["x0"] * zoom, w["top"] * zoom, w["x1"] * zoom, w["bottom"] * zoom],
                }
                for w in words
            ]
            page_text = " ".join([w["text"] for w in words])
            layout = {"width": img_pil.width, "height": img_pil.height, "words": word_list}
            return page_text, layout

        # Try secondary native extraction if words is empty but text exists
        logger.info(f"[OCR] p.{page_num}: Native words empty, trying extract_text()")
        text_fallback = page.extract_text()
        if text_fallback and text_fallback.strip():
            logger.info(
                f"[OCR] p.{page_num}: Native extract_text succeeded (length: {len(text_fallback)})"
            )
            layout = {"width": img_pil.width, "height": img_pil.height, "words": []}
            return text_fallback, layout

        # Fallback to Vision OCR
        logger.warning(f"[OCR] p.{page_num}: No native text found. Falling back to Vision API")
        try:
            from src.providers.vision_ocr import VisionOCRService

            vision = VisionOCRService()
            if vision.is_available():
                logger.info(f"[OCR] p.{page_num}: Using Vision API for extraction")
                text, layout = await vision.detect_text_with_layout(img_bytes)
                if layout:
                    logger.info(f"[OCR] p.{page_num}: Vision API successful")
                    layout.update({"width": img_pil.width, "height": img_pil.height})
                    return text, layout
                else:
                    logger.warning(f"[OCR] p.{page_num}: Vision API returned no layout/text")
            else:
                logger.warning(
                    f"[OCR] p.{page_num}: Vision API is not available (check credentials)"
                )
        except Exception as e:
            logger.error(f"[OCR] p.{page_num}: Vision OCR failed: {e}")

        # Final fallback to Gemini
        logger.warning(
            f"[OCR] p.{page_num}: All native/Vision attempts failed. Falling back to Gemini"
        )
        try:
            from src.prompts import PDF_EXTRACT_TEXT_OCR_PROMPT

            text = await self.ai_provider.generate_with_image(
                PDF_EXTRACT_TEXT_OCR_PROMPT, img_bytes, "image/png", model=self.model
            )
            if text and text.strip():
                logger.info(f"[OCR] p.{page_num}: Gemini OCR successful (length: {len(text)})")
                return text, None
            else:
                logger.error(f"[OCR] p.{page_num}: Gemini OCR returned empty text")
                return "", None
        except Exception as e:
            logger.error(f"[OCR] p.{page_num}: Gemini OCR failed: {e}")
            return "", None

    def _finalize_ocr(self, file_hash, filename, all_text_parts, all_layout_parts=None):
        """Save final OCR output to database."""
        full_text = "\n\n---\n\n".join(all_text_parts)
        layout_json = json.dumps(all_layout_parts) if all_layout_parts else None
        save_ocr_to_db(
            file_hash=file_hash,
            filename=filename,
            ocr_text=full_text,
            model_name=self.model,
            layout_json=layout_json,
        )
        logger.info(f"[OCR Streaming] Completed and saved: {filename}")
