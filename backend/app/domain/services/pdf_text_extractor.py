from __future__ import annotations

from typing import Any

from common.logger import ServiceLogger

log = ServiceLogger("OCR")


def extract_links(page, zoom: float) -> list[dict]:
    """PDFページのメタデータからハイパーリンクを抽出する。

    TODO: linkify-it-py でテキスト中の生URL（アノテーションなし）も検出する。
    """
    log.debug("extract_links", "Extracting links", page_num=page.page_number, zoom=zoom)
    links = []
    try:
        if hasattr(page, "hyperlinks"):
            for link in page.hyperlinks:
                if link.get("uri"):
                    links.append({
                        "url": link["uri"],
                        "bbox": [
                            link["x0"] * zoom,
                            link["top"] * zoom,
                            link["x1"] * zoom,
                            link["bottom"] * zoom,
                        ],
                    })
        if not links and hasattr(page, "annots"):
            for annot in page.annots:
                uri = annot.get("uri") or (
                    annot.get("A", {}).get("URI") if "A" in annot else None
                )
                if uri:
                    links.append({
                        "url": uri,
                        "bbox": [
                            annot["x0"] * zoom,
                            annot["top"] * zoom,
                            annot["x1"] * zoom,
                            annot["bottom"] * zoom,
                        ],
                    })
    except Exception as e:
        log.warning(
            "extract_links",
            "Link extraction failed",
            page_num=page.page_number,
            error=str(e),
        )
    return links


def extract_markdown_sequential(
    file_bytes: bytes, idx: int, exclude_bboxes_pt: list
) -> str:
    """各スレッドで独立した fitz doc を開いて PyMuPDF4LLM で Markdown 抽出する。"""
    import fitz  # noqa: PLC0415

    doc = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        return _extract_markdown_inner(doc, idx, exclude_bboxes_pt)
    finally:
        doc.close()


def _extract_markdown_inner(doc: Any, idx: int, exclude_bboxes_pt: list) -> str:
    import fitz  # noqa: PLC0415
    import pymupdf4llm  # noqa: PLC0415

    page_obj = doc[idx]

    # 明示的に指定された figure/table bbox のみを除外する。
    # page_obj.get_drawings() からの自動検出はテキスト列の枠線を誤検出するため廃止。
    if exclude_bboxes_pt:
        for bbox_pt in exclude_bboxes_pt:
            page_obj.add_redact_annot(fitz.Rect(*bbox_pt))
        page_obj.apply_redactions()

    return pymupdf4llm.to_markdown(
        doc,
        pages=[idx],
        show_progress=False,
        write_images=False,
    )
