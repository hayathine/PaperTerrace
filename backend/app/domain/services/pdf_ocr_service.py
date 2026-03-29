from __future__ import annotations

import asyncio
import io
import json
import os
import re
import tempfile
import time
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
    フォントエンコーディング由来の文字化けが含まれるか判定する。

    以下の4パターンをカバーする:

    1. (cid:N) ― pdfplumber が ToUnicode CMap 欠損時に出力するリテラル文字列。
    2. Unicode 置換文字 U+FFFD ― デコード失敗を示す明示的マーカー。
    3. Unicode Private Use Area U+E000〜U+F8FF ― PDFカスタムフォントが
       グリフをPUA領域にマッピングする場合に発生（本PDFの主因）。
    4. Unicode Supplementary PUA U+F0000〜U+FFFFF ― 同上、補助面版。

    各パターンについて「5文字以上」または「テキスト全体の0.5%以上」で
    文字化けと判定する。
    """
    if not text:
        return False

    text_len = max(len(text), 1)
    threshold_ratio = 0.005

    # 1. (cid:N) パターン
    cid_count = text.count("(cid:")
    if cid_count >= 5 or (cid_count > 0 and cid_count / text_len > threshold_ratio):
        return True

    # 2. Unicode 置換文字 U+FFFD
    repl_count = text.count("\ufffd")
    if repl_count >= 5 or (repl_count > 0 and repl_count / text_len > threshold_ratio):
        return True

    # 3. Unicode Private Use Area (BMP): U+E000〜U+F8FF
    pua_count = sum(1 for c in text if "\ue000" <= c <= "\uf8ff")
    if pua_count >= 5 or (pua_count > 0 and pua_count / text_len > threshold_ratio):
        return True

    # 4. Unicode Supplementary PUA: U+F0000〜U+FFFFF
    sup_pua_count = sum(1 for c in text if "\U000f0000" <= c <= "\U000fffff")
    if sup_pua_count >= 5 or (
        sup_pua_count > 0 and sup_pua_count / text_len > threshold_ratio
    ):
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
        file_hash = "unknown"
        tmp_path = None
        try:
            file_hash = _get_file_hash(file_bytes)

            log.info(
                "extract_start",
                "Starting OCR extraction (Batched & Persistent File)",
                filename=filename,
                file_hash=file_hash,
                file_size=len(file_bytes),
                user_plan=user_plan,
            )

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
                processing_metrics = {}  # {page_num: {"p12": duration, "p3": duration}}

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

                    # Phase 1+2 タスクをチャンク内全ページ分作成（並列実行）
                    phase12_tasks = [
                        asyncio.create_task(
                            self._prepare_page_phases_1_2(
                                pdf.pages[page_idx],
                                page_idx,
                                total_pages,
                                file_hash,
                                file_bytes,
                            )
                        )
                        for page_idx in range(chunk_start, chunk_end)
                    ]

                    # Phase 1+2: 並列実行済みタスクをページ順に収集しつつ即時 yield
                    chunk_page_data = []
                    for task in phase12_tasks:
                        t_p12_start = time.perf_counter()
                        page_data = (
                            await task
                        )  # 並列実行済みのタスクをページ順に受け取る
                        t_p12_end = time.perf_counter()
                        duration = round(t_p12_end - t_p12_start, 3)
                        pn = page_data["page_num"]
                        if pn not in processing_metrics:
                            processing_metrics[pn] = {}
                        processing_metrics[pn]["p12"] = duration

                        log.debug(
                            "extract_text_streaming",
                            "Phase 1 & 2 done",
                            page_num=pn,
                            duration=duration,
                        )
                        p = page_data["phase1_result"]
                        yield (
                            p[0],
                            p[1],
                            p[2],
                            p[3],
                            p[4],
                            page_data["image_url"],
                            p[6],
                        )
                        chunk_page_data.append(page_data)

                    # バッチOCR: phase1 テキストが空または文字化けのページを事前検出して一括送信
                    _min_len = int(settings.get("INFERENCE_OCR_MIN_PAGE_TEXT_LEN", 100))
                    ocr_candidate_pages = [
                        (pd["page_num"], pd["img_bytes"])
                        for pd in chunk_page_data
                        if not (pd.get("phase1_result") or ("",) * 7)[2].strip()
                        or _is_garbled_text(
                            (pd.get("phase1_result") or ("",) * 7)[2] or ""
                        )
                        or len(
                            ((pd.get("phase1_result") or ("",) * 7)[2] or "").strip()
                        )
                        < _min_len
                    ]
                    batch_ocr_results: dict[int, tuple[str, list[dict]]] = {}
                    if ocr_candidate_pages:
                        try:
                            batch_ocr_results = await self._ocr_fallback_batch(
                                ocr_candidate_pages
                            )
                            log.info(
                                "batch_ocr",
                                "Batch OCR completed",
                                candidate_count=len(ocr_candidate_pages),
                                result_count=len(batch_ocr_results),
                            )
                            for pd in chunk_page_data:
                                if pd["page_num"] in batch_ocr_results:
                                    pd["ocr_text_override"] = batch_ocr_results[
                                        pd["page_num"]
                                    ]
                        except Exception as e:
                            log.error(
                                "batch_ocr",
                                "Target batch OCR failed completely",
                                error=str(e),
                            )

                    phase3_tasks = [
                        asyncio.create_task(
                            self._finalize_page_phase_3(
                                page_data,
                                [],
                                None,
                                page_data["page_num"] - 1,
                                total_pages,
                                file_hash,
                                pdf_path=tmp_path,
                                file_bytes=file_bytes,
                                ocr_text_override=page_data.get("ocr_text_override"),
                            )
                        )
                        for page_data in chunk_page_data
                    ]

                    # Phase 3 結果も完了次第 yield し、DB 保存用に page_num 順で収集
                    chunk_finals = []
                    for task in asyncio.as_completed(phase3_tasks):
                        t_p3_start = time.perf_counter()
                        final_result = await task
                        t_p3_end = time.perf_counter()
                        if final_result:
                            pn = final_result[0]
                            duration = round(t_p3_end - t_p3_start, 3)
                            if pn not in processing_metrics:
                                processing_metrics[pn] = {}
                            processing_metrics[pn]["p3"] = duration

                            log.debug(
                                "extract_text_streaming",
                                "Phase 3 completed (OCR/Finalize)",
                                page_num=pn,
                                duration=duration,
                            )
                            yield final_result
                        chunk_finals.append(final_result)

                    chunk_finals.sort(key=lambda r: r[0])
                    for final_result in chunk_finals:
                        all_text_parts.append(final_result[2])
                        all_layout_parts.append(final_result[6])

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
                metrics=processing_metrics,
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
        t_start = time.perf_counter()
        page_num = page_idx + 1
        is_last = page_idx == total_pages - 1
        resolution = int(settings.get("PDF_DPI", "200"))
        zoom = resolution / 72.0

        log.debug("_prepare_page_phases_1_2", "Phase 1 & 2 start", page_num=page_num)

        # Phase 1: Native Text & Links
        try:
            t_extract_start = time.perf_counter()
            native_words = page.extract_words(
                use_text_flow=True, x_tolerance=1, y_tolerance=3
            )
            page_text = page.extract_text() or ""
            t_extract_end = time.perf_counter()
            log.debug(
                "_prepare_page_phases_1_2",
                "Native text extraction done",
                page_num=page_num,
                duration=round(t_extract_end - t_extract_start, 3),
            )
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
        t_end = time.perf_counter()
        log.debug(
            "_prepare_page_phases_1_2",
            "Phase 1 & 2 completed",
            page_num=page_num,
            total_duration=round(t_end - t_start, 3),
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
        ocr_text_override: tuple[str, list[dict]] | None = None,
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

                # テキストが空（スキャン PDF）、(cid:N) 文字化け、または極端に短い場合は OCR フォールバックへ
                is_empty = not page_text.strip()
                # pymupdf4llm はフォントエンコーディングエラーを ASCII シフト文字として出力するため
                # そのパターンを検出できない場合がある。pdfplumber (Phase 1) は \uFFFD を出力するため
                # 両方をチェックして文字化けを正確に判定する。
                phase1_text = (
                    page_data.get("phase1_result") or ("", "", "", "", "", "", "")
                )[2] or ""
                is_garbled = _is_garbled_text(page_text) or _is_garbled_text(
                    phase1_text
                )
                _min_page_text_len = int(
                    settings.get("INFERENCE_OCR_MIN_PAGE_TEXT_LEN", 100)
                )
                is_too_short = (
                    not is_empty and len(page_text.strip()) < _min_page_text_len
                )

                log.info(
                    "_finalize_page_phase_3",
                    "Checking OCR Fallback conditions",
                    page_num=page_num,
                    is_empty=is_empty,
                    is_garbled=is_garbled,
                    is_too_short=is_too_short,
                    page_text_len=len(page_text.strip()),
                    phase1_text_len=len(phase1_text.strip()),
                    min_page_text_len=_min_page_text_len,
                )

                if is_empty or is_garbled or is_too_short:
                    reason = (
                        "empty_text"
                        if is_empty
                        else "garbled_text"
                        if is_garbled
                        else "too_short_text"
                    )
                    if ocr_text_override is not None:
                        # バッチOCRで事前取得済みのテキストと word bbox を使用
                        log.info(
                            "_finalize_page_phase_3",
                            "Using pre-fetched batch OCR result",
                            reason=reason,
                            page_num=page_num,
                        )
                        ocr_text, ocr_words = ocr_text_override
                        if ocr_text:
                            page_text = ocr_text
                        if ocr_words:
                            layout_data["words"] = ocr_words
                    else:
                        log.warning(
                            "_finalize_page_phase_3",
                            "OCR fallback triggered",
                            reason=reason,
                            page_num=page_num,
                            text_len=len(page_text.strip()),
                            cid_count=page_text.count("(cid:"),
                        )
                        fallback_text, fallback_words = await self._ocr_fallback(
                            page_data["img_bytes"],
                            page_num,
                            layout_blocks=layout_blocks,
                            img_width=int(layout_data.get("width", 0)),
                            img_height=int(layout_data.get("height", 0)),
                        )
                        log.info(
                            "_finalize_page_phase_3",
                            "OCR fallback results retrieved",
                            page_num=page_num,
                            fallback_text_len=len(fallback_text) if fallback_text else 0,
                            fallback_words_count=len(fallback_words) if fallback_words else 0,
                        )
                        if fallback_text:
                            page_text = fallback_text
                        if fallback_words:
                            layout_data["words"] = fallback_words

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

    @staticmethod
    def _make_line_bboxes_from_layout(
        layout_blocks: list,
        img_width: int,
        img_height: int,
        line_height: int,
    ) -> list[dict]:
        """レイアウトブロックを水平ラインストリップに分割して OCR 用 bbox リストを生成する。

        各テキスト系ブロックを line_height px のストリップに縦分割する。
        図・グラフ等の非テキストブロックは除外する。
        """
        NON_TEXT_CLASSES = {"figure", "picture", "chart", "image", "seal"}
        bboxes: list[dict] = []

        for block in layout_blocks:
            class_name = block.get("class_name", "").lower()
            if any(cls in class_name for cls in NON_TEXT_CLASSES):
                continue

            raw_bbox = block.get("bbox", {})
            if not isinstance(raw_bbox, dict):
                continue

            x_min = max(0, int(raw_bbox.get("x_min", 0)))
            y_min = max(0, int(raw_bbox.get("y_min", 0)))
            x_max = min(img_width, int(raw_bbox.get("x_max", img_width)))
            y_max = min(img_height, int(raw_bbox.get("y_max", img_height)))

            if x_max <= x_min or y_max <= y_min:
                continue

            # ブロックを line_height px のストリップに縦分割
            y = y_min
            while y < y_max:
                strip_y_max = min(y + line_height, y_max)
                # 高さが line_height の半分未満のストリップは認識精度が低いため除外
                if (strip_y_max - y) >= line_height // 2:
                    bboxes.append(
                        {
                            "x_min": x_min,
                            "y_min": y,
                            "x_max": x_max,
                            "y_max": strip_y_max,
                        }
                    )
                y += line_height

        return bboxes

    async def _ocr_fallback(
        self,
        img_bytes: bytes,
        page_num: int,
        layout_blocks: list | None = None,
        img_width: int = 0,
        img_height: int = 0,
    ) -> tuple[str, list[dict]]:
        """
        テキスト抽出が失敗した場合に推論サービス経由で Tesseract フォールバック OCR を実行する。
        """
        from app.providers.inference_client import get_ocr_client

        try:
            log.info(
                "_ocr_fallback",
                "Tesseract OCR fallback via Inference Service",
                page_num=page_num,
            )
            t_start = time.perf_counter()

            client = await get_ocr_client()
            text, words_list = await client.ocr_page(img_bytes)

            log.debug(
                "_ocr_fallback",
                "Tesseract OCR fallback completed",
                page_num=page_num,
                duration=round(time.perf_counter() - t_start, 3),
                word_count=len(words_list),
                text_len=len(text.strip()),
            )
            return text.strip(), words_list

        except Exception as e:
            log.warning(
                "_ocr_fallback",
                "Tesseract OCR fallback failed",
                page_num=page_num,
                error=str(e),
            )
            return "", []

    async def _ocr_fallback_batch(
        self,
        pages: list[tuple[int, bytes]],
    ) -> dict[int, tuple[str, list[dict]]]:
        """
        複数ページ画像を並列で Tesseract OCR し結果を返す。

        Args:
            pages: [(page_num, img_bytes), ...] のリスト

        Returns:
            {page_num: (ocr_text, words)} の辞書。失敗ページは含まない。
        """
        if not pages:
            return {}

        log.info(
            "_ocr_fallback_batch",
            "Tesseract parallel OCR",
            page_nums=[p[0] for p in pages],
        )

        results_list = await asyncio.gather(
            *[self._ocr_fallback(img_bytes, page_num) for page_num, img_bytes in pages],
            return_exceptions=True,
        )

        results: dict[int, tuple[str, list[dict]]] = {}
        for (page_num, _), result in zip(pages, results_list):
            if isinstance(result, Exception):
                log.warning(
                    "_ocr_fallback_batch",
                    "Page OCR failed",
                    page_num=page_num,
                    error=str(result),
                )
                continue
            text, words = result
            if text:
                results[page_num] = (text, words)

        log.info(
            "_ocr_fallback_batch",
            "Batch OCR completed",
            requested=[p[0] for p in pages],
            parsed=list(results.keys()),
        )
        return results

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
            # ページ全体を覆う背景矩形（>80%）はredact対象外にする
            if area > page_area * 0.80:
                continue
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
            from common.dspy_seed_prompt import PDF_EXTRACT_TEXT_OCR_PROMPT

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
