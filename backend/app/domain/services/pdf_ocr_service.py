from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tempfile
from collections.abc import AsyncGenerator
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

from app.crud import get_ocr_from_db, save_ocr_to_db
from app.providers import get_ai_provider
from app.providers.image_storage import async_save_page_image, get_page_images
from app.utils import _get_file_hash
from common import settings
from common.logger import ServiceLogger
from common.utils.bbox import scale_bbox

from .figure_service import FigureService
from .language_service import LanguageService

log = ServiceLogger("OCR")


def _is_garbled_text(text: str) -> bool:
    """
    (cid:N) やフォントエンコーディング由来の文字化けが含まれるか判定する。

    PDFのToUnicode CMAPが欠損・破損している場合、pdfplumberやPyMuPDFは
    グリフをUnicodeにマッピングできず (cid:N) をそのまま出力する。
    5個以上、またはテキスト全体の0.5%以上を占める場合に化けと判定する。
    """
    if not text:
        return False
    cid_count = text.count("(cid:")
    if cid_count >= 5:
        return True
    if cid_count > 0 and cid_count / max(len(text), 1) > 0.005:
        return True
    return False


def _fix_indentation_artifacts(text: str) -> str:
    """
    2段組みPDFから生じるインデントアーティファクトを修正する。

    pymupdf4llmが2段組みレイアウトを処理する際、右カラムのテキストが
    大きなインデントとして抽出され、Markdownのコードブロックとして
    誤レンダリングされる問題を解決する。
    """
    lines = text.split("\n")
    result = []
    for line in lines:
        # 4スペース以上のインデントがある行（Markdownコードブロックの条件）
        if (
            len(line) > 4
            and line.startswith("    ")
            and not line.startswith("        ")
        ):
            stripped = line.lstrip()
            # Markdownの構造要素（見出し、引用、リスト、コードフェンス等）は変更しない
            if stripped and stripped[0] not in "#>-*+|`":
                # コードらしき記号の割合を検査
                code_chars = sum(1 for c in stripped if c in "{}()[];=><!/\\@$%^&")
                ratio = code_chars / max(len(stripped), 1)
                # コード記号が10%未満なら自然言語テキストとみなしインデントを除去
                if ratio < 0.10:
                    result.append(stripped)
                    continue
        result.append(line)
    return "\n".join(result)


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
        """Processes PDF pages in chunks for efficiency while streaming results."""
        file_hash = _get_file_hash(file_bytes)

        log.info(
            "extract_start",
            "Starting OCR extraction (Batched & Persistent File)",
            filename=filename,
            file_hash=file_hash,
            file_size=len(file_bytes),
            user_plan=user_plan,
        )

        tmp_path = None
        try:
            # 1. Cache handling
            cached_result = await self._handle_cache(file_hash)
            if cached_result:
                storage_type = settings.get("STORAGE_TYPE", "local").upper()
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

            # PDFバイトの診断ログ（magic bytes確認）
            magic = file_bytes[:8] if file_bytes else b""
            is_valid_pdf = bool(file_bytes) and b"%PDF" in file_bytes[:16]
            log.info(
                "pdf_open",
                "PDFを開きます",
                file_hash=file_hash,
                size=len(file_bytes),
                magic_hex=magic.hex(),
                is_valid_pdf=is_valid_pdf,
            )
            if not file_bytes:
                raise ValueError("PDFバイトが空です (GCSからの取得に失敗した可能性)")
            if not is_valid_pdf:
                raise ValueError(
                    f"無効なPDFフォーマット: magic bytes={magic.hex()}"
                    f" size={len(file_bytes)}"
                )

            # Save to temporary file for pdfplumber (text extraction)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            import pdfplumber  # noqa: PLC0415 (遅延インポート: 起動時メモリ削減)

            with pdfplumber.open(tmp_path) as pdf:
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

                # --- Chunked Processing (Batch AI + Persistent File) ---
                CHUNK_SIZE = int(settings.get("OCR_CHUNK_SIZE", "5"))
                for chunk_start in range(0, total_pages, CHUNK_SIZE):
                    chunk_end = min(chunk_start + CHUNK_SIZE, total_pages)
                    log.info(
                        "chunk_start",
                        "Processing chunk",
                        chunk=f"{chunk_start + 1}-{chunk_end}",
                        total=total_pages,
                    )

                    # Step A: Phase 1 & 2 を chunk 内全ページ並列実行
                    # 各ページが独立した fitz doc でレンダリングするため真の並列動作する
                    prefetched_pages = list(
                        await asyncio.gather(
                            *[
                                self._prepare_page_phases_1_2(
                                    pdf.pages[page_idx],
                                    page_idx,
                                    total_pages,
                                    file_hash,
                                    file_bytes,
                                )
                                for page_idx in range(chunk_start, chunk_end)
                            ]
                        )
                    )

                    # Step B: Phase 1 を全ページ先行 yield → Phase 3 を chunk 内並列実行
                    # Phase 3 も独立 fitz doc を使うため並列化可能
                    for page_data in prefetched_pages:
                        yield page_data["phase1_result"]

                    finalize_tasks = [
                        asyncio.create_task(
                            self._finalize_page_phase_3(
                                prefetched_pages[i],
                                [],
                                None,
                                chunk_start + i,
                                total_pages,
                                file_hash,
                                pdf_path=tmp_path,
                                file_bytes=file_bytes,
                            )
                        )
                        for i in range(len(prefetched_pages))
                    ]

                    for final_result in await asyncio.gather(*finalize_tasks):
                        page_text = final_result[2]
                        layout_data = final_result[6]
                        all_text_parts.append(page_text)
                        all_layout_parts.append(layout_data)
                        yield final_result

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
                exc_info=True,
            )
            error_msg = str(e)
            from app.core.config import is_production

            if is_production():
                error_msg = "Internal Server Error during OCR"
            yield (0, 0, f"ERROR_API_FAILED: {error_msg}", True, file_hash, None, None)
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    async def _handle_cache(self, file_hash: str) -> list | None:
        """Check if OCR is cached and return formatted pages if so."""
        log.debug("_handle_cache", "Checking cache", file_hash=file_hash)
        cache_data = get_ocr_from_db(file_hash)
        if not cache_data:
            log.info("_handle_cache", "Cache miss", file_hash=file_hash)
            return None

        storage_type = settings.get("STORAGE_TYPE", "local").upper()
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

    async def _prepare_page_phases_1_2(
        self, page, page_idx, total_pages, file_hash, file_bytes: bytes = b""
    ) -> dict:
        """Execute Phase 1 & 2: Native text extraction and image rendering."""
        page_num = page_idx + 1
        is_last = page_idx == total_pages - 1
        resolution = int(settings.get("PDF_DPI", "200"))
        zoom = resolution / 72.0

        log.debug("_prepare_page_phases_1_2", "Phase 1 & 2 start", page_num=page_num)

        # Phase 1: Native Text & Links
        try:
            native_words = page.extract_words(
                use_text_flow=True, x_tolerance=1, y_tolerance=3
            )
            page_text = page.extract_text() or ""
        except Exception as e:
            log.warning(
                "_prepare_page_phases_1_2",
                "Text extraction failed",
                page_num=page_num,
                error=str(e),
            )
            native_words = []
            page_text = ""

        links = self._extract_links(page, zoom)

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

        phase1_result = (
            page_num,
            total_pages,
            page_text,
            is_last,
            file_hash,
            None,
            layout_data,
        )

        # Phase 2: Page Image (各スレッドで独立した fitz doc を開いて並列レンダリング)
        def _render_and_encode(file_bytes_inner: bytes, page_idx_inner: int, res: int):
            import fitz as _fitz  # noqa: PLC0415
            from PIL import Image as _Image  # noqa: PLC0415

            _doc = _fitz.open(stream=file_bytes_inner, filetype="pdf")
            try:
                mat = _fitz.Matrix(res / 72.0, res / 72.0)
                _page = _doc[page_idx_inner]
                pix = _page.get_pixmap(matrix=mat)
                pil = _Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
            finally:
                _doc.close()
            buf = io.BytesIO()
            pil.save(buf, format="JPEG", quality=85)
            return pil, buf.getvalue()

        img_pil, img_bytes = await asyncio.to_thread(
            _render_and_encode, file_bytes, page_idx, resolution
        )
        image_url = await async_save_page_image(file_hash, page_num, img_bytes, "jpg")

        # Update layout data coordinates with actual image scale
        scale_x = img_pil.width / float(page.width)
        scale_y = img_pil.height / float(page.height)
        layout_data["width"] = float(img_pil.width)
        layout_data["height"] = float(img_pil.height)
        layout_data["words"] = [
            {
                "word": w["text"],
                "bbox": scale_bbox(
                    [w["x0"], w["top"], w["x1"], w["bottom"]], scale_x, scale_y
                ).to_list(),
            }
            for w in native_words
        ]

        return {
            "page_num": page_num,
            "page": page,
            "zoom": zoom,
            "img_pil": img_pil,
            "img_bytes": img_bytes,
            "image_url": image_url,
            "layout_data": layout_data,
            "phase1_result": phase1_result,
        }

    async def _finalize_page_phase_3(
        self,
        page_data: dict,
        layout_blocks: list,
        fitz_doc: Any,
        page_idx: int,
        total_pages: int,
        file_hash: str,
        pdf_path: str | None = None,
        file_bytes: bytes = b"",
    ) -> tuple:
        """Execute Phase 3: Layout refinement, Markdown generation, and Figure cropping."""
        page_num = page_data["page_num"]
        layout_data = page_data["layout_data"]
        img_pil = page_data["img_pil"]
        image_url = page_data["image_url"]
        zoom = page_data["zoom"]
        is_last = page_idx == total_pages - 1

        log.debug("_finalize_page_phase_3", "Phase 3 start", page_num=page_num)

        try:
            if pdf_path:
                # 1. Figure/Table Bbox collection
                figure_table_bboxes_pt = []
                for block in layout_blocks:
                    class_name = block.get("class_name", "").lower()
                    if (
                        class_name
                        in [
                            "figure",
                            "picture",
                            "chart",
                            "table",
                            "algorithm",
                            "formula",
                            "equation",
                        ]
                        and "caption" not in class_name
                    ):
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

                # 2. Markdown extraction (独立した fitz doc でスレッド実行)
                raw_md = await asyncio.to_thread(
                    self._extract_markdown_sequential,
                    file_bytes,
                    page_idx,
                    figure_table_bboxes_pt,
                )

                page_text = re.sub(r"!\[.*?\]\(.*?\)", "", raw_md).strip()

                # 2段組みレイアウトによるインデントアーティファクトを修正
                page_text = _fix_indentation_artifacts(page_text)

                # (cid:N) 等の文字化けを検出したら OCR フォールバックへ
                if _is_garbled_text(page_text):
                    log.warning(
                        "_finalize_page_phase_3",
                        "Garbled text detected (cid: pattern), attempting OCR fallback",
                        page_num=page_num,
                        cid_count=page_text.count("(cid:"),
                    )
                    fallback = await self._ocr_fallback(
                        page_data["img_bytes"], page_num
                    )
                    if fallback:
                        page_text = fallback

                # 3. Post-process layout blocks (equations, figures)
                # y座標を保持して後で本文中の適切な位置に挿入するため、リストで管理する
                figures_with_y: list[tuple[float, str]] = []
                fig_idx = 0

                # ページ高さをレイアウト座標系で取得（y座標の正規化に使用）
                page_height_layout = (
                    max(
                        (
                            block.get("bbox", {}).get("y_max", 0)
                            if isinstance(block.get("bbox"), dict)
                            else (
                                block.get("bbox", [0, 0, 0, 0])[3]
                                if len(block.get("bbox", [])) > 3
                                else 0
                            )
                        )
                        for block in layout_blocks
                    )
                    if layout_blocks
                    else 1
                )

                for block in layout_blocks:
                    class_name = block.get("class_name", "").lower()
                    bbox = block.get("bbox", {})
                    bx1, by1, bx2, by2 = (
                        (
                            bbox.get("x_min", 0),
                            bbox.get("y_min", 0),
                            bbox.get("x_max", 0),
                            bbox.get("y_max", 0),
                        )
                        if isinstance(bbox, dict)
                        else bbox
                    )
                    bbox_list = [bx1, by1, bx2, by2]

                    # Figure/Table/Formula cropping and metadata
                    if (
                        class_name
                        in [
                            "figure",
                            "picture",
                            "chart",
                            "table",
                            "algorithm",
                            "formula",
                            "equation",
                        ]
                        and "caption" not in class_name
                    ):
                        # ページ境界・縦線の誤検知フィルタ（極端なアスペクト比を除外）
                        width = bx2 - bx1
                        height = by2 - by1
                        if height > 0:
                            aspect = width / height
                        else:
                            aspect = 999
                        # 幅が10px未満 or アスペクト比が0.05未満（ほぼ垂直線）は除外
                        if width < 10 or aspect < 0.05:
                            continue

                        # URLにangle bracketsを付けてスペース・特殊文字を含むURLを安全に表現
                        bbox_md = f"{bx1},{by1},{bx2},{by2}"
                        figure_ref = f"![{class_name}](<{bbox_md}>)"
                        figures_with_y.append((by1, figure_ref))
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
                                crop_img.save(
                                    buf, format="JPEG", quality=85, optimize=True
                                )
                                img_name = f"p{page_num}_{class_name.replace(' ', '_')}_{fig_idx}"
                                fig_url = await async_save_page_image(
                                    file_hash, img_name, buf.getvalue(), "jpg"
                                )
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
                                "_finalize_page_phase_3",
                                "Crop failed",
                                class_name=class_name,
                                error=str(crop_err),
                            )

                # 図・表をy座標に基づいて本文中の適切な位置に挿入する
                if figures_with_y:
                    paragraphs = [p for p in page_text.split("\n\n") if p.strip()]
                    if not paragraphs:
                        page_text = "\n\n".join(
                            ref for _, ref in sorted(figures_with_y, key=lambda x: x[0])
                        )
                    else:
                        total_height = max(page_height_layout, 1)
                        offset = 0
                        for by1_val, ref in sorted(figures_with_y, key=lambda x: x[0]):
                            y_frac = by1_val / total_height
                            insert_idx = min(
                                int(y_frac * len(paragraphs)) + offset,
                                len(paragraphs),
                            )
                            paragraphs.insert(insert_idx, ref)
                            offset += 1
                        page_text = "\n\n".join(paragraphs)
            else:
                # Fallback implementation
                from app.domain.services.markdown_builder import (
                    generate_markdown_from_layout,
                )

                page_text = generate_markdown_from_layout(
                    layout_data["words"], layout_blocks
                )

        except Exception as e:
            log.error(
                "_finalize_page_phase_3",
                "Failed to finalize page",
                page_num=page_num,
                error=str(e),
                exc_info=True,
            )
            page_text = page_data["phase1_result"][2]  # Use Phase 1 text as fallback

        return (
            page_num,
            total_pages,
            page_text,
            is_last,
            file_hash,
            image_url,
            layout_data,
        )

    async def _ocr_fallback(self, img_bytes: bytes, page_num: int) -> str:
        """
        フォントエンコーディング問題でテキスト抽出が失敗した場合に
        Vision OCR → Gemini OCR の順でフォールバックしてプレーンテキストを返す。
        """
        # 1. Vision OCR
        try:
            from app.providers.vision_ocr import VisionOCRService

            vision = VisionOCRService()
            if vision.is_available():
                log.info(
                    "_ocr_fallback",
                    "Falling back to Vision OCR due to garbled text",
                    page_num=page_num,
                )
                text, _ = await vision.detect_text_with_layout(img_bytes)
                if text and text.strip():
                    return text
        except Exception as e:
            log.warning(
                "_ocr_fallback",
                "Vision OCR fallback failed",
                page_num=page_num,
                error=str(e),
            )

        # 2. Gemini OCR
        try:
            from common.prompts import PDF_EXTRACT_TEXT_OCR_PROMPT

            log.info(
                "_ocr_fallback",
                "Falling back to Gemini OCR due to garbled text",
                page_num=page_num,
            )
            text = await self.ai_provider.generate_with_image(
                PDF_EXTRACT_TEXT_OCR_PROMPT,
                img_bytes,
                "image/jpeg",
                model=self.model,
            )
            if text and text.strip():
                return text
        except Exception as e:
            log.warning(
                "_ocr_fallback",
                "Gemini OCR fallback failed",
                page_num=page_num,
                error=str(e),
            )

        return ""

    def _extract_markdown_sequential(
        self, file_bytes: bytes, idx: int, exclude_bboxes_pt: list
    ) -> str:
        """各スレッドで独立した fitz doc を開いて PyMuPDF4LLM で Markdown 抽出する。"""
        import fitz  # noqa: PLC0415 (遅延インポート: 起動時メモリ削減)

        doc = fitz.open(stream=file_bytes, filetype="pdf")
        try:
            return self._extract_markdown_inner(doc, idx, exclude_bboxes_pt)
        finally:
            doc.close()

    def _extract_markdown_inner(
        self, doc: Any, idx: int, exclude_bboxes_pt: list
    ) -> str:
        import fitz  # noqa: PLC0415
        import pymupdf4llm  # noqa: PLC0415

        page_obj = doc[idx]
        page_area = page_obj.rect.width * page_obj.rect.height

        all_exclude = list(exclude_bboxes_pt)
        for drawing in page_obj.get_drawings():
            rect = drawing["rect"]
            area = rect.width * rect.height
            aspect = rect.width / rect.height if rect.height > 0 else 999
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
                PDF_EXTRACT_TEXT_OCR_PROMPT, img_bytes, "image/webp", model=self.model
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
