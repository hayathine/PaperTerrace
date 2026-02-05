import base64
import io
import json
import os
import tempfile
from collections.abc import AsyncGenerator

import pdfplumber
from app.crud import get_ocr_from_db, save_ocr_to_db
from app.logger import get_service_logger, logger
from app.providers import get_ai_provider
from app.providers.image_storage import get_page_images, save_page_image
from app.utils import _get_file_hash

from .figure_service import FigureService
from .language_service import LanguageService

log = get_service_logger("OCR")


class PDFOCRService:
    def __init__(self, model):
        self.ai_provider = get_ai_provider()
        self.model = model
        self.figure_service = FigureService(self.ai_provider, self.model)
        self.language_service = LanguageService(self.ai_provider, self.model)

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

        tmp_path = None
        try:
            logger.debug(f"[OCR] Creating temp file for {file_hash}")
            # Save PDF to temporary file for libraries that need a path (like Camelot)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            logger.debug(f"[OCR] Temp file created at {tmp_path}. Opening PDF...")

            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                total_pages = len(pdf.pages)
                logger.info(f"[OCR] PDF opened. Total pages: {total_pages}")

                all_text_parts = []
                all_layout_parts = []

                for page_num in range(total_pages):
                    logger.debug(f"[OCR] Starting processing page {page_num + 1}/{total_pages}")

                    async for result in self._process_page_incremental(
                        pdf.pages[page_num], page_num, total_pages, file_hash, pdf_path=tmp_path
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
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def _handle_cache(self, file_hash: str) -> list | None:
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
                    "phase2",  # Add phase information for cached data
                )
            )

        # Add COORDINATES_READY event for cached data
        pages.append(
            (0, len(cached_images), "COORDINATES_READY", True, file_hash, None, None, "status")
        )

        return pages

    async def _process_page_incremental(
        self, page, page_idx, total_pages, file_hash, pdf_path: str | None = None
    ):
        """Process a single page in 3 phases: Text, Image, Analysis."""
        page_num = page_idx + 1
        is_last = page_idx == total_pages - 1

        # We use a standard zoom for coordinates (72 dpi -> 300 dpi)
        resolution = 300
        zoom = resolution / 72.0

        # Phase 1: Native Text & Links (ULTRA FAST)
        logger.debug(f"[OCR] Page {page_num}: Phase 1 - Extraction text/links")
        native_words = page.extract_words(use_text_flow=True, x_tolerance=1, y_tolerance=3)
        links = self._extract_links(page, zoom)

        # Create initial layout data (coordinates only)
        # pdfplumber page.width/height is in points (72dpi), scale it to zoom
        layout_data = {
            "width": float(page.width) * zoom,
            "height": float(page.height) * zoom,
            "words": [
                {
                    "word": w["text"],
                    "bbox": [w["x0"] * zoom, w["top"] * zoom, w["x1"] * zoom, w["bottom"] * zoom],
                }
                for w in native_words
            ],
            "links": links,
        }
        page_text = page.extract_text()

        yield (page_num, total_pages, page_text, is_last, file_hash, None, layout_data)

        # Phase 2: Page Image (FAST)
        logger.debug(f"[OCR] Page {page_num}: Phase 2 - Rendering image")
        page_img = page.to_image(resolution=resolution, antialias=True)
        img_pil = page_img.original.convert("RGB")

        buffer = io.BytesIO()
        img_pil.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()

        page_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
        image_url = save_page_image(file_hash, page_num, page_image_b64)

        yield (page_num, total_pages, page_text, is_last, file_hash, image_url, layout_data)

        # Phase 3: AI Figure Extraction (HEAVY)
        logger.debug(f"[OCR] Page {page_num}: Phase 3 - AI Analysis")
        figures = await self.figure_service.detect_and_extract_figures(
            img_bytes,
            page_img,
            page,
            file_hash,
            page_num,
            zoom=zoom,
            pdf_path=pdf_path,
        )

        if figures:
            if "figures" not in layout_data:
                layout_data["figures"] = []
            layout_data["figures"].extend(figures)

        yield (page_num, total_pages, page_text, is_last, file_hash, image_url, layout_data)

    def _extract_links(self, page, zoom):
        """Extract hyperlinks from the PDF page metadata using pdfplumber."""
        links = []
        try:
            # pdfplumber >= 0.11.0 has .hyperlinks
            # It already contains the URI and the bounding box
            if hasattr(page, "hyperlinks"):
                for link in page.hyperlinks:
                    if link.get("uri"):
                        links.append(
                            {
                                "url": link["uri"],
                                "bbox": [
                                    link["x0"] * zoom,
                                    link["top"] * zoom,
                                    link["x1"] * zoom,
                                    link["bottom"] * zoom,
                                ],
                            }
                        )
            # Fallback to annots if hyperlinks is not populated or available
            if not links and hasattr(page, "annots"):
                for annot in page.annots:
                    # Check for URI specifically in the annotation dictionary
                    uri = annot.get("uri") or (
                        annot.get("A", {}).get("URI") if "A" in annot else None
                    )
                    if uri:
                        links.append(
                            {
                                "url": uri,
                                "bbox": [
                                    annot["x0"] * zoom,
                                    annot["top"] * zoom,
                                    annot["x1"] * zoom,
                                    annot["bottom"] * zoom,
                                ],
                            }
                        )
        except Exception as e:
            logger.warning(f"Link extraction failed on page {page.page_number}: {e}")
        return links

    async def _extract_native_or_vision_text(
        self, page, img_bytes, img_pil, zoom, exclude_bboxes=None
    ):
        """Try to extract text from PDF directly, fallback to Vision API or Gemini."""
        page_num = page.page_number
        logger.debug(f"[OCR] p.{page_num}: Attempting native word extraction")

        words = page.extract_words(use_text_flow=True, x_tolerance=1, y_tolerance=3)
        if words:
            # Filter words that are inside any figure bbox
            if exclude_bboxes:
                filtered_words = []
                for w in words:
                    # Convert word coords to zoom coords for comparison
                    wx_center = (w["x0"] + w["x1"]) / 2 * zoom
                    wy_center = (w["top"] + w["bottom"]) / 2 * zoom

                    is_inside = False
                    for b in exclude_bboxes:
                        # b is [x1, y1, x2, y2] in zoom/px coords
                        if b[0] <= wx_center <= b[2] and b[1] <= wy_center <= b[3]:
                            is_inside = True
                            break
                    if not is_inside:
                        filtered_words.append(w)
                words = filtered_words

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
            from app.providers.vision_ocr import VisionOCRService

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
            from app.domain.prompts import PDF_EXTRACT_TEXT_OCR_PROMPT

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
