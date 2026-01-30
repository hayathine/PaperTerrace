import base64
from typing import AsyncGenerator, Optional

import fitz  # PyMuPDF

from src.crud import get_ocr_from_db, save_ocr_to_db
from src.logger import logger
from src.prompts import (
    PDF_EXTRACT_TEXT_OCR_PROMPT,
)
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
            pdf_doc = fitz.open(stream=file_bytes, filetype="pdf")
            total_pages = len(pdf_doc)
            all_text_parts = []

            for page_num in range(total_pages):
                result = await self._process_page(pdf_doc, page_num, total_pages, file_hash)
                page_text = result[2]
                all_text_parts.append(page_text)
                yield result

            pdf_doc.close()

            # 2. Finalize and save to DB
            self._finalize_ocr(file_hash, filename, all_text_parts)

        except Exception as e:
            logger.error(f"OCR streaming failed: {e}")
            yield (0, 0, f"ERROR_API_FAILED: {str(e)}", True, file_hash, None, None)

    async def _handle_cache(self, file_hash: str) -> Optional[list]:
        """Check for existing OCR results."""
        cached_ocr = get_ocr_from_db(file_hash)
        if not cached_ocr:
            return None

        cached_images = get_page_images(file_hash)
        if not cached_images:
            logger.info("Cached OCR text found but images missing. Regenerating.")
            return None

        logger.info("Returning cached OCR text and images.")
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

    async def _process_page(self, pdf_doc, page_idx, total_pages, file_hash):
        """Process a single page: render image, OCR, detect layout/figures."""
        page_num = page_idx + 1
        page = pdf_doc[page_idx]

        # Render image
        zoom = 2.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)
        img_bytes = pix.tobytes("png")
        page_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
        image_url = save_page_image(file_hash, page_num, page_image_b64)

        # Extract native text/layout
        page_text, layout_data = await self._extract_native_or_vision_text(
            page, img_bytes, pix, zoom
        )

        # Figure extraction
        figures = await self.figure_service.detect_and_extract_figures(
            img_bytes, pix, file_hash, page_num
        )
        if figures:
            if not layout_data:
                layout_data = {"width": pix.width, "height": pix.height, "words": []}
            if "figures" not in layout_data:
                layout_data["figures"] = []
            layout_data["figures"].extend(figures)

        is_last = page_idx == total_pages - 1
        return (page_num, total_pages, page_text, is_last, file_hash, image_url, layout_data)

    async def _extract_native_or_vision_text(self, page, img_bytes, pix, zoom):
        """Try to extract text from PDF directly, fallback to Vision API or Gemini."""
        words = page.get_text("words")
        if words:
            word_list = [
                {"word": w[4], "bbox": [w[0] * zoom, w[1] * zoom, w[2] * zoom, w[3] * zoom]}
                for w in words
            ]
            page_text = " ".join([w[4] for w in words])
            layout = {"width": pix.width, "height": pix.height, "words": word_list}
            return page_text, layout

        # Fallback to Vision OCR
        logger.info(f"[OCR] No text on page {page.number + 1}, trying Vision API")
        try:
            from src.providers.vision_ocr import VisionOCRService

            vision = VisionOCRService()
            if vision.is_available():
                text, layout = await vision.detect_text_with_layout(img_bytes)
                if layout:
                    layout.update({"width": pix.width, "height": pix.height})
                    return text, layout
        except Exception as e:
            logger.error(f"Vision OCR failed: {e}")

        # Final fallback to Gemini
        logger.info(f"[OCR] Falling back to Gemini for page {page.number + 1}")
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
