from __future__ import annotations

import asyncio
import io
import re

from common.logger import ServiceLogger
from common.utils.text import fix_indentation_artifacts

log = ServiceLogger("OCR")


async def ocr_fallback(
    img_bytes: bytes,
    page_num: int,
    layout_blocks: list | None = None,
    img_width: int = 0,
    img_height: int = 0,
) -> tuple[str, list[dict]]:
    """テキスト抽出が失敗した場合に推論サービス経由で Tesseract フォールバック OCR を実行する。"""
    import time  # noqa: PLC0415

    from app.providers.inference_client import get_ocr_client  # noqa: PLC0415

    try:
        client = await get_ocr_client()
        log.info(
            "ocr_fallback",
            "Tesseract OCR fallback via Inference Service",
            page_num=page_num,
            ocr_url=client.ocr_url,
            is_disabled=client.is_disabled,
            circuit_open=client._cb.get("circuit_open", False),
            failure_count=client._cb.get("failure_count", 0),
        )
        t_start = time.perf_counter()
        text, words_list = await client.ocr_page(img_bytes)
        log.info(
            "ocr_fallback",
            "Tesseract OCR fallback completed",
            page_num=page_num,
            duration=round(time.perf_counter() - t_start, 3),
            word_count=len(words_list),
            text_len=len(text.strip()),
        )
        return text.strip(), words_list
    except Exception as e:
        log.warning(
            "ocr_fallback",
            "Tesseract OCR fallback failed",
            page_num=page_num,
            error=str(e),
        )
        return "", []


async def ocr_fallback_batch(
    pages: list[tuple[int, bytes]],
) -> dict[int, tuple[str, list[dict]]]:
    """複数ページ画像を並列で Tesseract OCR し結果を返す。

    Args:
        pages: [(page_num, img_bytes), ...] のリスト

    Returns:
        {page_num: (ocr_text, words)} の辞書。失敗ページは含まない。
    """
    if not pages:
        return {}

    log.info(
        "ocr_fallback_batch",
        "Tesseract parallel OCR",
        page_nums=[p[0] for p in pages],
    )

    results_list = await asyncio.gather(
        *[ocr_fallback(img_bytes, page_num) for page_num, img_bytes in pages],
        return_exceptions=True,
    )

    results: dict[int, tuple[str, list[dict]]] = {}
    for (page_num, _), result in zip(pages, results_list):
        if isinstance(result, Exception):
            log.warning(
                "ocr_fallback_batch",
                "Page OCR failed",
                page_num=page_num,
                error=str(result),
            )
            continue
        text, words = result
        if text:
            results[page_num] = (text, words)

    log.info(
        "ocr_fallback_batch",
        "Batch OCR completed",
        requested=[p[0] for p in pages],
        parsed=list(results.keys()),
    )
    return results


async def run_batch_ocr_for_chunk(
    ocr_candidate_pages: list[tuple[int, bytes]],
    file_bytes: bytes,
    ocrmypdf_task: "asyncio.Task | None",
    ocrmypdf_result: "dict[int, tuple[str, list[dict]]] | None",
) -> "tuple[dict[int, tuple[str, list[dict]]], asyncio.Task | None, dict[int, tuple[str, list[dict]]] | None]":
    """OCR 候補ページのバッチ OCR を実行する。

    OCRmyPDF タスクの起動・待機・Tesseract フォールバックを内包し、
    タスクと結果キャッシュを次チャンクへ引き継げるよう返す。

    Args:
        ocr_candidate_pages: (page_num, img_bytes) のリスト
        file_bytes: 元 PDF バイト列（OCRmyPDF 入力用）
        ocrmypdf_task: 既存の OCRmyPDF タスク（None なら初回）
        ocrmypdf_result: 前チャンクで取得済みの結果（None なら未取得）

    Returns:
        (batch_ocr_results, updated_task, updated_result) のタプル
    """
    candidate_page_nums = [pn for pn, _ in ocr_candidate_pages]
    log.info(
        "batch_ocr",
        "OCR候補ページ検出",
        candidate_count=len(ocr_candidate_pages),
        candidate_pages=candidate_page_nums,
    )

    batch_ocr_results: dict[int, tuple[str, list[dict]]] = {}

    if ocrmypdf_task is None:
        ocrmypdf_task = asyncio.create_task(run_ocrmypdf(file_bytes))
        log.info(
            "batch_ocr",
            "OCRmyPDFタスク起動",
            pdf_size=len(file_bytes),
            trigger_page=candidate_page_nums[0],
        )

    if ocrmypdf_result is None:
        log.info("batch_ocr", "OCRmyPDF結果を待機中...")
        try:
            ocrmypdf_result = await ocrmypdf_task
            log.info(
                "batch_ocr",
                "OCRmyPDF結果取得完了",
                page_count=len(ocrmypdf_result),
                pages_with_text=sorted(ocrmypdf_result.keys()),
            )
        except Exception as e:
            log.warning("batch_ocr", "OCRmyPDF失敗 → Tesseractへフォールバック", error=str(e))
            ocrmypdf_result = {}

    if ocrmypdf_result:
        for pn, _img in ocr_candidate_pages:
            if pn in ocrmypdf_result:
                ocr_text, ocr_words = ocrmypdf_result[pn]
                batch_ocr_results[pn] = (ocr_text, ocr_words)
                log.info(
                    "batch_ocr",
                    "OCRmyPDF結果適用",
                    page_num=pn,
                    text_len=len(ocr_text),
                    word_count=len(ocr_words),
                )

    remaining = [
        (pn, img) for pn, img in ocr_candidate_pages if pn not in batch_ocr_results
    ]
    if remaining:
        log.info(
            "batch_ocr",
            "Tesseractフォールバック対象",
            page_nums=[pn for pn, _ in remaining],
        )
        try:
            fallback_results = await ocr_fallback_batch(remaining)
            batch_ocr_results.update(fallback_results)
            log.info(
                "batch_ocr",
                "Tesseractフォールバック完了",
                success_pages=list(fallback_results.keys()),
            )
        except Exception as e:
            log.error("batch_ocr", "Target batch OCR failed completely", error=str(e))

    log.info(
        "batch_ocr",
        "Batch OCR completed",
        candidate_count=len(ocr_candidate_pages),
        result_count=len(batch_ocr_results),
        missing_pages=[pn for pn, _ in ocr_candidate_pages if pn not in batch_ocr_results],
    )
    return batch_ocr_results, ocrmypdf_task, ocrmypdf_result


async def run_ocrmypdf(file_bytes: bytes) -> dict[int, tuple[str, list[dict]]]:
    """OCRmyPDFでサーチャブルPDFを生成し、ページごとのテキスト辞書を返す。

    Returns:
        {page_num(1始まり): (text, words)} の辞書。OCR失敗ページは含まない。
    """
    import time  # noqa: PLC0415

    from app.providers.inference_client import get_ocr_client  # noqa: PLC0415

    client = await get_ocr_client()
    log.info(
        "run_ocrmypdf",
        "OCRmyPDFリクエスト送信",
        pdf_size=len(file_bytes),
        ocr_url=client.ocr_url,
        is_disabled=client.is_disabled,
    )
    t_start = time.perf_counter()

    searchable_pdf = await client.ocr_pdf(file_bytes)

    if not searchable_pdf:
        log.warning(
            "run_ocrmypdf",
            "OCRmyPDF失敗: Noneが返却されました（inference-ocrサービス未応答または無効）",
            ocr_url=client.ocr_url,
        )
        return {}

    duration = round(time.perf_counter() - t_start, 3)
    log.info(
        "run_ocrmypdf",
        "OCRmyPDFサーチャブルPDF取得完了",
        duration=duration,
        input_size=len(file_bytes),
        output_size=len(searchable_pdf),
    )

    result: dict[int, tuple[str, list[dict]]] = {}
    import fitz  # noqa: PLC0415
    import pdfplumber  # noqa: PLC0415
    import pymupdf4llm  # noqa: PLC0415

    fitz_doc = fitz.open(stream=searchable_pdf, filetype="pdf")
    total = fitz_doc.page_count
    try:
        with pdfplumber.open(io.BytesIO(searchable_pdf)) as pdf_p:
            for i in range(total):
                plumber_page = pdf_p.pages[i] if i < len(pdf_p.pages) else None
                words: list[dict] = []
                if plumber_page is not None:
                    raw_words = plumber_page.extract_words(
                        use_text_flow=True, x_tolerance=1, y_tolerance=3
                    )
                    words = [
                        {
                            "word": w["text"],
                            "bbox": [w["x0"], w["top"], w["x1"], w["bottom"]],
                            "conf": 1.0,
                        }
                        for w in raw_words
                        if w["text"].strip()
                    ]

                try:
                    md = pymupdf4llm.to_markdown(
                        fitz_doc,
                        pages=[i],
                        show_progress=False,
                        write_images=False,
                        force_text=True,  # OCRmyPDFの隠しテキスト層も確実に抽出
                    )
                    md_text = re.sub(r"!\[.*?\]\(.*?\)", "", md).strip()
                    md_text = fix_indentation_artifacts(md_text)
                    log.info(
                        "run_ocrmypdf",
                        "ページMarkdown変換完了",
                        page_num=i + 1,
                        total_pages=total,
                        md_len=len(md_text),
                        has_text=bool(md_text),
                        word_count=len(words),
                    )
                    if md_text:
                        result[i + 1] = (md_text, words)
                    elif words:
                        # Markdown抽出は空だがwordsがある場合はテキストを再構成
                        fallback_text = " ".join(w["word"] for w in words)
                        result[i + 1] = (fallback_text, words)
                except Exception as page_err:
                    log.warning(
                        "run_ocrmypdf",
                        "pymupdf4llm変換失敗、pdfplumberにフォールバック",
                        page_num=i + 1,
                        error=str(page_err),
                    )
                    if plumber_page is not None:
                        text = (plumber_page.extract_text() or "").strip()
                        if text:
                            result[i + 1] = (text, words)
    finally:
        fitz_doc.close()

    log.info(
        "run_ocrmypdf",
        "全ページMarkdown変換完了",
        total_pages=total,
        extracted_pages=len(result),
        empty_pages=total - len(result),
    )
    return result
