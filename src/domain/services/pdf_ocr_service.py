import base64
import io
from typing import AsyncGenerator, Optional

import pdfplumber

from src.core.logger import logger
from src.core.utils import _get_file_hash
from src.domain.prompts import (
    PDF_EXTRACT_TEXT_OCR_PROMPT,
)
from src.infra import get_ai_provider
from src.infra.crud import get_ocr_from_db, save_ocr_to_db
from src.infra.image_storage import get_page_images, save_page_image

from .pdf.abstract_service import AbstractService
from .pdf.figure_service import FigureService


class PDFOCRService:
    def __init__(self, model):
        self.ai_provider = get_ai_provider()
        self.model = model
        self.figure_service = FigureService(self.ai_provider, self.model)

    async def extract_text_streaming(
        self, file_bytes: bytes, filename: str = "unknown.pdf", user_plan: str = "free"
    ) -> AsyncGenerator:
        """Processes PDF pages one by one and streams results."""
        file_hash = _get_file_hash(file_bytes)

        # 1. Cache handling
        cached_result = await self._handle_cache(file_hash, file_bytes)
        if cached_result:
            for page in cached_result:
                yield page
            return

        logger.info(f"--- AI OCR Streaming: {filename} ---")

        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                total_pages = len(pdf.pages)
                all_text_parts = []

                import time

                for page_num in range(total_pages):
                    page_start = time.time()
                    logger.info(
                        f"[OCR] Starting page {page_num + 1}/{total_pages} (hash: {file_hash[:8]})"
                    )
                    try:
                        result = await self._process_page(
                            pdf, page_num, total_pages, file_hash, file_bytes
                        )
                        page_elapsed = time.time() - page_start
                        logger.info(
                            f"[OCR] Finished page {page_num + 1}/{total_pages} in {page_elapsed:.2f}s"
                        )
                        page_text = result[2]
                        all_text_parts.append(page_text)
                        yield result
                    except Exception as page_err:
                        logger.exception(f"[OCR] Error processing page {page_num + 1}")
                        if page_num == 0:
                            raise page_err
                        continue

            # 2. Finalize and save to DB
            self._finalize_ocr(file_hash, filename, all_text_parts)

        except Exception as e:
            logger.error(f"OCR streaming failed: {e}")
            yield (0, 0, f"ERROR_API_FAILED: {str(e)}", True, file_hash, None, None)

    def fast_extract_text(self, file_bytes: bytes) -> str:
        """Rapidly extract native text from all pages for Text Mode."""
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                all_text = []
                for page in pdf.pages:
                    txt = page.extract_text(use_text_flow=True, x_tolerance=1, y_tolerance=3)
                    if txt:
                        all_text.append(txt)
                return "\n\n---\n\n".join(all_text)
        except Exception as e:
            logger.error(f"Fast text extraction failed: {e}")
            return ""

    def extract_abstract_text(self, file_bytes: bytes) -> Optional[str]:
        """Extract abstract using specialized service."""
        return AbstractService.extract_abstract(file_bytes)

    async def _handle_cache(self, file_hash: str, file_bytes: bytes) -> Optional[list]:
        """Check for existing OCR results and verify all pages are present."""
        cached_ocr = get_ocr_from_db(file_hash)
        if not cached_ocr:
            return None

        cached_images = get_page_images(file_hash)
        if not cached_images:
            logger.info("Cached OCR text found but images missing. Regenerating.")
            return None

        # Verify page count to ensure all pages are displayed
        try:
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                total_pdf_pages = len(pdf.pages)

                if len(cached_images) < total_pdf_pages:
                    logger.info(
                        f"Incomplete cache: {len(cached_images)}/{total_pdf_pages} pages. Regenerating."
                    )
                    return None
        except Exception as e:
            logger.warning(f"Failed to verify PDF page count for cache: {e}")

        logger.info(f"Returning cached OCR text and {len(cached_images)} images.")
        total_pages = len(cached_images)
        pages = []
        for i, img_url in enumerate(cached_images):
            pages.append(
                (
                    i + 1,
                    total_pages,
                    cached_ocr if i == 0 else "",
                    i == total_pages - 1,
                    file_hash,
                    img_url,
                    None,
                )
            )
        return pages

    async def _process_page(
        self, pdf, page_idx, total_pages, file_hash, pdf_bytes: Optional[bytes] = None
    ):
        """Process a single page: render image, OCR, detect layout/figures."""
        page_num = page_idx + 1
        page = pdf.pages[page_idx]

        # Render image
        try:
            logger.debug(f"[OCR] Rendering image for page {page_num}")
            # pdfplumber rendering (requires Pillow)
            im = page.to_image(resolution=300)
            img_pil = im.original

            img_byte_arr = io.BytesIO()
            img_pil.save(img_byte_arr, format="PNG")
            img_bytes = img_byte_arr.getvalue()

            page_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
            image_url = save_page_image(file_hash, page_num, page_image_b64)
            logger.debug(f"[OCR] Page {page_num} image saved: {image_url}")
        except Exception:
            logger.exception(f"[OCR] Failed to render image for page {page_num}")
            raise

        # Extract native text/layout
        try:
            logger.debug(f"[OCR] Extracting text for page {page_num}")
            page_text, layout_data = await self._extract_native_or_vision_text(
                page, img_bytes, img_pil
            )
            logger.debug(f"[OCR] Page {page_num} text extracted (length: {len(page_text)})")
        except Exception as e:
            logger.warning(f"[OCR] Text extraction failed for page {page_num}: {e}")
            page_text = ""
            layout_data = None

        # Figure extraction
        try:
            logger.debug(f"[OCR] Detecting figures for page {page_num}")
            figures = await self.figure_service.detect_and_extract_figures(
                img_bytes, img_pil, file_hash, page_num, pdf_bytes, float(page.height)
            )
            if figures:
                logger.info(f"[OCR] Page {page_num} detected {len(figures)} figures")
                if not layout_data:
                    layout_data = {"width": img_pil.width, "height": img_pil.height, "words": []}
                if "figures" not in layout_data:
                    layout_data["figures"] = []
                layout_data["figures"].extend(figures)
        except Exception as e:
            logger.error(f"[OCR] Figure extraction failed for page {page_num}: {e}", exc_info=True)

        # 明示的なメモリ解放
        import gc

        del img_pil
        del img_byte_arr
        del img_bytes
        gc.collect()

        is_last = page_idx == total_pages - 1
        return (page_num, total_pages, page_text, is_last, file_hash, image_url, layout_data)

    async def _extract_native_or_vision_text(self, page, img_bytes, img_pil):
        """Try to extract text from PDF directly, fallback to Vision API or Gemini."""
        scale = img_pil.width / float(page.width)

        words = page.extract_words(use_text_flow=True, x_tolerance=1, y_tolerance=3)
        if words:
            word_list = [
                {
                    "word": w["text"],
                    "bbox": [
                        w["x0"] * scale,
                        w["top"] * scale,
                        w["x1"] * scale,
                        w["bottom"] * scale,
                    ],
                }
                for w in words
            ]
            page_text = page.extract_text(use_text_flow=True, x_tolerance=1, y_tolerance=3)
            layout = {"width": img_pil.width, "height": img_pil.height, "words": word_list}
            return page_text, layout

        # Fallback to Vision OCR
        logger.info(f"[OCR] No text on page {page.page_number}, trying Vision API")
        try:
            from src.infra.vision_ocr import VisionOCRService

            vision = VisionOCRService()
            if vision.is_available():
                text, layout = await vision.detect_text_with_layout(img_bytes)
                if layout:
                    layout.update({"width": img_pil.width, "height": img_pil.height})
                    return text, layout
        except Exception as e:
            logger.error(f"Vision OCR failed: {e}")

        # Final fallback to Gemini
        logger.info(f"[OCR] Falling back to Gemini for page {page.page_number}")
        try:
            text = await self.ai_provider.generate_with_image(
                PDF_EXTRACT_TEXT_OCR_PROMPT, img_bytes, "image/png", model=self.model
            )
            return text, None
        except Exception as e:
            logger.error(f"Gemini OCR failed: {e}")
            return "", None

    def _finalize_ocr(self, file_hash, filename, all_text_parts):
        """Save final OCR output to database."""
        full_text = "\n\n---\n\n".join(all_text_parts)
        save_ocr_to_db(
            file_hash=file_hash,
            filename=filename,
            ocr_text=full_text,
            model_name=self.model,
        )
        logger.info(f"[OCR Streaming] Completed and saved: {filename}")
