import asyncio
import base64
import io
import json
import os
import re
import tempfile
from collections.abc import AsyncGenerator

import fitz  # PyMuPDF
import pdfplumber
import pymupdf4llm

from app.crud import get_ocr_from_db, save_ocr_to_db
from app.providers import get_ai_provider
from app.providers.image_storage import get_page_images, save_page_image
from app.utils import _get_file_hash
from common.logger import ServiceLogger
from common.utils.bbox import scale_bbox
from common.utils.math_latex import (
    convert_superscript_brackets,
    replace_equation_paragraph,
    wrap_equation_block,
)

from .figure_service import FigureService
from .language_service import LanguageService

log = ServiceLogger("OCR")


class PDFOCRService:
    """
    PDF OCR Service
    アップロードされた論文をOCR処理する
    """

    def __init__(self, model):
        self.ai_provider = get_ai_provider()
        self.model = model
        self.figure_service = FigureService(self.ai_provider, self.model)
        self.language_service = LanguageService(self.ai_provider, self.model)

    async def extract_text_streaming(
        self, file_bytes: bytes, filename: str = "unknown.pdf", user_plan: str = "free"
    ) -> AsyncGenerator:
        """Processes PDF pages one by one and streams results."""
        file_hash = _get_file_hash(file_bytes)

        log.info(
            "extract_start",
            "Starting OCR extraction",
            filename=filename,
            file_hash=file_hash,
            file_size=len(file_bytes),
            user_plan=user_plan,
        )

        # 1. Cache handling
        cached_result = await self._handle_cache(file_hash)
        if cached_result:
            storage_type = os.getenv("STORAGE_TYPE", "local").upper()
            log.info(
                "cache_hit",
                "Using cached OCR",
                filename=filename,
                storage_type=storage_type,
                file_hash=file_hash,
            )

            for page in cached_result:
                yield page
            return

        log.info(
            "cache_miss",
            "No cache found, starting AI OCR",
            filename=filename,
            file_hash=file_hash,
        )

        tmp_path = None
        try:
            log.debug("temp_file_create", "Creating temp file", file_hash=file_hash)

            # Save PDF to temporary file for libraries that need a path (like Camelot)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name
            log.debug("temp_file_created", "Temp file created", tmp_path=tmp_path)

            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                total_pages = len(pdf.pages)
                log.info(
                    "pdf_opened",
                    "PDF opened successfully",
                    file_hash=file_hash,
                    total_pages=total_pages,
                    filename=filename,
                )

                all_text_parts = []
                all_layout_parts = []

                for page_num in range(total_pages):
                    log.debug(
                        "page_start",
                        "Processing page",
                        page_num=page_num + 1,
                        total_pages=total_pages,
                    )

                    async for result in self._process_page_incremental(
                        pdf.pages[page_num],
                        page_num,
                        total_pages,
                        file_hash,
                        pdf_path=tmp_path,
                    ):
                        # result is (page_num+1, total_pages, page_text, is_last, file_hash, img_url, layout_data)
                        if (
                            result[5] is not None
                        ):  # Final result per page (img_url valid)
                            page_text = result[2]
                            layout_data = result[6]
                            all_text_parts.append(page_text)
                            all_layout_parts.append(layout_data)
                            log.info(
                                "page_complete",
                                "Page processed",
                                page_num=page_num + 1,
                                text_length=len(page_text),
                            )

                        yield result

            # 2. Finalize and save to DB
            log.info(
                "finalize_start", "Finalizing OCR and saving to DB", file_hash=file_hash
            )
            self._finalize_ocr(file_hash, filename, all_text_parts, all_layout_parts)
            log.info(
                "extract_complete",
                "OCR extraction completed",
                filename=filename,
                file_hash=file_hash,
                total_pages=total_pages,
            )

        except Exception as e:
            log.error(
                "extract_failed",
                "OCR streaming failed",
                error=str(e),
                file_hash=file_hash,
                error_type=type(e).__name__,
            )

            log.error("extract_failed", "Full traceback", error=str(e), exc_info=True)

            yield (0, 0, f"ERROR_API_FAILED: {str(e)}", True, file_hash, None, None)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
                log.debug("temp_file_cleanup", "Temp file removed", tmp_path=tmp_path)

    async def _handle_cache(self, file_hash: str) -> list | None:
        """Check if OCR is cached and return formatted pages if so."""
        log.debug("_handle_cache", "Checking cache", file_hash=file_hash)
        cache_data = get_ocr_from_db(file_hash)
        if not cache_data:
            log.info("_handle_cache", "Cache miss", file_hash=file_hash)
            return None

        storage_type = os.getenv("STORAGE_TYPE", "local").upper()
        log.info(
            "_handle_cache", "Cache hit", storage_type=storage_type, file_hash=file_hash
        )

        ocr_text = cache_data["ocr_text"]
        layout_json = cache_data.get("layout_json")
        layout_data_list = []
        if layout_json:
            try:
                layout_data_list = json.loads(layout_json)
            except Exception:
                log.warning(
                    "_handle_cache",
                    "Failed to parse layout_json from cache",
                    file_hash=file_hash,
                )

        # Basic split by separator
        pages_text = ocr_text.split("\n\n---\n\n")
        cached_images = get_page_images(file_hash)
        if not cached_images:
            log.info(
                "_handle_cache",
                "Cache hit for text but images missing. Recalculating.",
                file_hash=file_hash,
            )
            return None

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

        # Add COORDINATES_READY event for cached data
        pages.append(
            (
                0,
                len(cached_images),
                "COORDINATES_READY",
                True,
                file_hash,
                None,
                None,
            )
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
        log.debug(
            "_process_page_incremental",
            "Phase 1 - Extraction text/links",
            page_num=page_num,
        )

        # Some PDFs have malformed font dictionaries that cause pdfminer to raise
        # PDFSyntaxError ("Invalid dictionary construct"). Catch it here so the page
        # can still be rendered as an image even when text extraction fails.
        try:
            native_words = page.extract_words(
                use_text_flow=True, x_tolerance=1, y_tolerance=3
            )
            page_text = page.extract_text()
        except Exception as e:
            log.warning(
                "_process_page_incremental",
                "Text extraction failed for page, falling back to image-only",
                page_num=page_num,
                error=str(e),
                error_type=type(e).__name__,
            )
            native_words = []
            page_text = ""

        links = self._extract_links(page, zoom)

        # Create initial layout data (coordinates only)
        # pdfplumber page.width/height is in points (72dpi), scale it to zoom
        layout_data = {
            "width": float(page.width) * zoom,
            "height": float(page.height) * zoom,
            "words": [
                {
                    "word": w["text"],
                    "bbox": [
                        w["x0"] * zoom,
                        w["top"] * zoom,
                        w["x1"] * zoom,
                        w["bottom"] * zoom,
                    ],
                }
                for w in native_words
            ],
            "links": links,
            "figures": [],
        }

        yield (page_num, total_pages, page_text, is_last, file_hash, None, layout_data)

        # Phase 2: Page Image (FAST)
        log.debug(
            "_process_page_incremental", "Phase 2 - Rendering image", page_num=page_num
        )

        page_img = page.to_image(resolution=resolution, antialias=True)
        img_pil = page_img.original.convert("RGB")

        buffer = io.BytesIO()
        img_pil.save(buffer, format="PNG")
        img_bytes = buffer.getvalue()

        page_image_b64 = base64.b64encode(img_bytes).decode("utf-8")
        image_url = save_page_image(file_hash, page_num, page_image_b64)

        # Update layout data using actual image dimensions to ensure alignment
        scale_x = img_pil.width / float(page.width)
        scale_y = img_pil.height / float(page.height)

        log.debug(
            "_process_page_incremental",
            "Scaling factors and dimensions",
            page_num=page_num,
            scale_x=scale_x,
            scale_y=scale_y,
            img_size=f"{img_pil.width}x{img_pil.height}",
            page_size=f"{page.width}x{page.height}",
        )

        layout_data["width"] = float(img_pil.width)
        layout_data["height"] = float(img_pil.height)

        # Re-scale words with precise factors
        layout_data["words"] = [
            {
                "word": w["text"],
                "bbox": scale_bbox(
                    [w["x0"], w["top"], w["x1"], w["bottom"]], scale_x, scale_y
                ).to_list(),
            }
            for w in native_words
        ]

        # Phase 3: Layout analysis and Markdown generation
        try:
            from app.domain.services.paddle_layout_service import get_layout_service

            layout_svc = get_layout_service()
            layout_blocks = await layout_svc.detect_layout_from_image_async(img_bytes)
            log.info(
                "_process_page_incremental",
                "Layout blocks detected",
                page_num=page_num,
                block_count=len(layout_blocks),
            )

            if pdf_path:
                # pymupdf4llm による高精度 Markdown 生成
                # Figure/Table の bbox 領域（画像px座標）を PDF ポイント座標へ変換して収集。
                figure_table_bboxes_pt = []
                for block in layout_blocks:
                    class_name = block.get("class_name", "").lower()
                    is_visual = class_name in [
                        "figure",
                        "picture",
                        "chart",
                        "table",
                        "algorithm",
                        "formula",
                        "equation",
                    ]
                    is_caption = "caption" in class_name
                    if is_visual and not is_caption:
                        bbox = block.get("bbox", {})
                        if isinstance(bbox, dict):
                            figure_table_bboxes_pt.append(
                                [
                                    bbox.get("x_min", 0) / zoom,
                                    bbox.get("y_min", 0) / zoom,
                                    bbox.get("x_max", 0) / zoom,
                                    bbox.get("y_max", 0) / zoom,
                                ]
                            )

                # fitz.Document はスレッドアンセーフなためページごとに開いて閉じる
                def _extract_md(path: str, idx: int, exclude_bboxes_pt: list) -> str:
                    doc = fitz.open(path)
                    try:
                        page_obj = doc[idx]
                        page_area = page_obj.rect.width * page_obj.rect.height

                        all_exclude = list(exclude_bboxes_pt)

                        # ベクターグラフィック（グラフ・チャート等）の除外。
                        # ページ面積の 1% 以上の描画パスを図表由来とみなす。
                        # 水平線・下線など細長い要素はアスペクト比でスキップ。
                        for drawing in page_obj.get_drawings():
                            rect = drawing["rect"]
                            area = rect.width * rect.height
                            aspect = (
                                rect.width / rect.height if rect.height > 0 else 999
                            )
                            if area > page_area * 0.01 and aspect < 20:
                                all_exclude.append([rect.x0, rect.y0, rect.x1, rect.y1])

                        if all_exclude:
                            for bbox_pt in all_exclude:
                                page_obj.add_redact_annot(fitz.Rect(*bbox_pt))
                            page_obj.apply_redactions()

                        return pymupdf4llm.to_markdown(
                            doc,
                            pages=[idx],
                            show_progress=False,
                            write_images=False,
                        )
                    finally:
                        doc.close()

                loop = asyncio.get_running_loop()
                raw_md = await loop.run_in_executor(
                    None, _extract_md, pdf_path, page_idx, figure_table_bboxes_pt
                )

                # pymupdf4llm が挿入した画像参照（![...](...)）を除去
                page_text = re.sub(r"!\[.*?\]\(.*?\)", "", raw_md).strip()

                # --- 数式後処理 -----------------------------------------------
                # 1. pymupdf4llm の [char] 上付き記法を ^{char} に変換
                #    例: Π[∗] → Π^{∗}, [x,m] → ^{x,m}
                #    純粋な数字列 [1],[12] は引用文献の可能性が高いため変換しない
                page_text = convert_superscript_brackets(page_text)

                # 2. レイアウト解析で equation と判定されたブロックを $$...$$ に置換
                #    layout_data["words"] からブロック内の単語を取得し、
                #    pymupdf4llm の対応段落を LaTeX ブロックで置換する
                for block in layout_blocks:
                    class_name = block.get("class_name", "").lower()
                    if not ("equation" in class_name or "formula" in class_name):
                        continue
                    bbox = block.get("bbox", {})
                    if isinstance(bbox, dict):
                        bx1 = bbox.get("x_min", 0)
                        by1 = bbox.get("y_min", 0)
                        bx2 = bbox.get("x_max", 0)
                        by2 = bbox.get("y_max", 0)
                    else:
                        bx1, by1, bx2, by2 = bbox
                    margin = 5
                    # ブロック内の OCR 単語を収集
                    eq_words = [
                        w["word"]
                        for w in layout_data["words"]
                        if (bx1 - margin)
                        <= (w["bbox"][0] + w["bbox"][2]) / 2
                        <= (bx2 + margin)
                        and (by1 - margin)
                        <= (w["bbox"][1] + w["bbox"][3]) / 2
                        <= (by2 + margin)
                    ]
                    if not eq_words:
                        continue
                    eq_raw = " ".join(eq_words)
                    latex_block = wrap_equation_block(eq_raw)
                    page_text, replaced = replace_equation_paragraph(
                        page_text, eq_words, latex_block
                    )
                    if not replaced:
                        # 対応段落が見つからない場合はページ末尾に追記
                        page_text += f"\n\n{latex_block}\n\n"
                # --------------------------------------------------------------

                # レイアウト解析で検出した Figure/Table の BBox プレースホルダーをページ末尾に追記
                # フロントエンドの TextModePage で遅延ローディング図画像として利用される
                figure_refs = []
                eq_count = 0
                fig_idx = 0
                for block in layout_blocks:
                    class_name = block.get("class_name", "").lower()

                    # Handle BBox Extraction
                    bbox = block.get("bbox", {})
                    if isinstance(bbox, dict):
                        bx1, by1, bx2, by2 = (
                            bbox.get("x_min", 0),
                            bbox.get("y_min", 0),
                            bbox.get("x_max", 0),
                            bbox.get("y_max", 0),
                        )
                    else:
                        bx1, by1, bx2, by2 = bbox
                    bbox_list = [bx1, by1, bx2, by2]

                    # Equations are now also treated as figures for border/extraction consistency

                    is_figure = class_name in [
                        "figure",
                        "picture",
                        "chart",
                        "table",
                        "algorithm",
                        "formula",
                        "equation",
                    ]
                    is_caption = "caption" in class_name

                    if is_figure and not is_caption:
                        figure_refs.append(f"\n\n![Figure]({bbox_list})\n")

                        # Issue 2: Immediate Figure/Table Frame Support
                        # Crop the figure now so it can be viewed immediately without lazy-loading
                        try:
                            margin = 5
                            crop_box = (
                                max(0, bx1 - margin),
                                max(0, by1 - margin),
                                min(img_pil.width, bx2 + margin),
                                min(img_pil.height, by2 + margin),
                            )
                            if crop_box[2] > crop_box[0] and crop_box[3] > crop_box[1]:
                                crop_img = img_pil.crop(crop_box)
                                buf = io.BytesIO()
                                crop_img.save(buf, format="JPEG", quality=85)
                                crop_b64 = base64.b64encode(buf.getvalue()).decode(
                                    "utf-8"
                                )

                                img_name = f"p{page_num}_{class_name.replace(' ', '_')}_{fig_idx}"
                                fig_url = save_page_image(file_hash, img_name, crop_b64)
                                fig_idx += 1

                                layout_data["figures"].append(
                                    {
                                        "page_num": page_num,
                                        "bbox": bbox_list,
                                        "label": class_name,
                                        "image_url": fig_url,
                                    }
                                )
                        except Exception as crop_err:
                            log.warning(
                                "_process_page_incremental",
                                "Failed to crop visual element",
                                class_name=class_name,
                                error=str(crop_err),
                            )

                if figure_refs:
                    page_text += "".join(figure_refs)

                log.info(
                    "_process_page_incremental",
                    "pymupdf4llm markdown generated",
                    page_num=page_num,
                    text_length=len(page_text),
                    figure_count=len(figure_refs),
                    equation_count=eq_count,
                )

            else:
                # pdf_path が取得できない場合は既存方式にフォールバック
                from app.domain.services.markdown_builder import (
                    generate_markdown_from_layout,
                )

                page_text = generate_markdown_from_layout(
                    layout_data["words"], layout_blocks
                )
                log.info(
                    "_process_page_incremental",
                    "Fallback markdown (generate_markdown_from_layout)",
                    page_num=page_num,
                )

        except Exception as e:
            log.error(
                "_process_page_incremental",
                "Markdown generation failed",
                page_num=page_num,
                error=str(e),
            )
            # Fallback to plain text if layout service fails

            pass

        # Debug: Verify words are correctly populated
        log.info(
            "_process_page_incremental",
            "Phase 2 complete",
            page_num=page_num,
            native_word_count=len(native_words),
            layout_word_count=len(layout_data["words"]),
            width=layout_data["width"],
            height=layout_data["height"],
            markdown_length=len(page_text),
        )

        if layout_data["words"]:
            sample_word = layout_data["words"][0]
            log.debug(
                "_process_page_incremental",
                "Sample word",
                page_num=page_num,
                sample=sample_word,
            )

        # Phase 2 yield with synchronized layout and image
        # Phase 3 (AI Analysis for figures) is now deferred to lazy loading
        yield (
            page_num,
            total_pages,
            page_text,
            is_last,
            file_hash,
            image_url,
            layout_data,
        )

    def _extract_links(self, page, zoom):  # TODO: `linkify-it-py`を検討
        """Extract hyperlinks from the PDF page metadata using pdfplumber."""
        log.debug(
            "_extract_links", "Extracting links", page_num=page.page_number, zoom=zoom
        )

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
            log.warning(
                "_extract_links",
                "Link extraction failed",
                page_num=page.page_number,
                error=str(e),
            )

        return links

    async def _extract_native_or_vision_text(
        self, page, img_bytes, img_pil, zoom, exclude_bboxes=None
    ):
        """Try to extract text from PDF directly, fallback to Vision API or Gemini."""
        page_num = page.page_number
        log.debug(
            "_extract_native_or_vision_text",
            "Attempting native word extraction",
            page_num=page_num,
        )

        words = page.extract_words(use_text_flow=True, x_tolerance=1, y_tolerance=3)
        if words:
            # Filter words that are inside any figure bbox
            if exclude_bboxes:
                log.debug(
                    "_extract_native_or_vision_text",
                    "Filtering words against figure boxes",
                    page_num=page_num,
                    box_count=len(exclude_bboxes),
                )

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

            log.info(
                "_extract_native_or_vision_text",
                "Native word extraction successful",
                page_num=page_num,
                word_count=len(words),
            )

            word_list = [
                {
                    "word": w["text"],
                    "bbox": [
                        w["x0"] * zoom,
                        w["top"] * zoom,
                        w["x1"] * zoom,
                        w["bottom"] * zoom,
                    ],
                }
                for w in words
            ]
            page_text = " ".join([w["text"] for w in words])
            layout = {
                "width": img_pil.width,
                "height": img_pil.height,
                "words": word_list,
            }
            return page_text, layout

        # Try secondary native extraction if words is empty but text exists
        log.info(
            "_extract_native_or_vision_text",
            "Native words empty, trying extract_text()",
            page_num=page_num,
        )
        text_fallback = page.extract_text()
        if text_fallback and text_fallback.strip():
            log.info(
                "_extract_native_or_vision_text",
                "Native extract_text succeeded",
                page_num=page_num,
                text_length=len(text_fallback),
            )

            layout = {"width": img_pil.width, "height": img_pil.height, "words": []}
            return text_fallback, layout

        # Fallback to Vision OCR
        log.warning(
            "_extract_native_or_vision_text",
            "No native text found. Falling back to Vision API",
            page_num=page_num,
        )

        try:
            from app.providers.vision_ocr import VisionOCRService

            vision = VisionOCRService()
            if vision.is_available():
                log.info(
                    "_extract_native_or_vision_text",
                    "Using Vision API for extraction",
                    page_num=page_num,
                )
                text, layout = await vision.detect_text_with_layout(img_bytes)
                if layout:
                    log.info(
                        "_extract_native_or_vision_text",
                        "Vision API successful",
                        page_num=page_num,
                    )
                    layout.update({"width": img_pil.width, "height": img_pil.height})
                    return text, layout
                else:
                    log.warning(
                        "_extract_native_or_vision_text",
                        "Vision API returned no layout/text",
                        page_num=page_num,
                    )
            else:
                log.warning(
                    "_extract_native_or_vision_text",
                    "Vision API is not available (check credentials)",
                    page_num=page_num,
                )

        except Exception as e:
            log.error(
                "_extract_native_or_vision_text",
                "Vision OCR failed",
                page_num=page_num,
                error=str(e),
            )

        # Final fallback to Gemini
        log.warning(
            "_extract_native_or_vision_text",
            "All native/Vision attempts failed. Falling back to Gemini",
            page_num=page_num,
        )

        try:
            from common.prompts import PDF_EXTRACT_TEXT_OCR_PROMPT

            text = await self.ai_provider.generate_with_image(
                PDF_EXTRACT_TEXT_OCR_PROMPT, img_bytes, "image/png", model=self.model
            )
            if text and text.strip():
                log.info(
                    "_extract_native_or_vision_text",
                    "Gemini OCR successful",
                    page_num=page_num,
                    text_length=len(text),
                )
                return text, None
            else:
                log.error(
                    "_extract_native_or_vision_text",
                    "Gemini OCR returned empty text",
                    page_num=page_num,
                )
                return "", None
        except Exception as e:
            log.error(
                "_extract_native_or_vision_text",
                "Gemini OCR failed",
                page_num=page_num,
                error=str(e),
            )
            return "", None

    def _finalize_ocr(self, file_hash, filename, all_text_parts, all_layout_parts=None):
        """Save final OCR output to database."""
        # Sanitize all strings to remove NUL bytes for PostgreSQL
        sanitized_text_parts = [
            p.replace("\0", "") if p else "" for p in all_text_parts
        ]
        full_text = "\n\n---\n\n".join(sanitized_text_parts)

        sanitized_layout = None
        if all_layout_parts:
            # We need to deeply sanitize the layout list/dict
            def sanitize_obj(obj):
                if isinstance(obj, str):
                    return obj.replace("\0", "")
                if isinstance(obj, list):
                    return [sanitize_obj(i) for i in obj]
                if isinstance(obj, dict):
                    return {k: sanitize_obj(v) for k, v in obj.items()}
                return obj

            sanitized_layout = sanitize_obj(all_layout_parts)
            layout_json = json.dumps(sanitized_layout)
        else:
            layout_json = None

        save_ocr_to_db(
            file_hash=file_hash,
            filename=filename.replace("\0", ""),
            ocr_text=full_text,
            model_name=self.model,
            layout_json=layout_json,
        )
        log.info("_finalize_ocr", "Completed and saved", filename=filename)
