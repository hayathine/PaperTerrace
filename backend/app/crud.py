from app.providers import get_storage_provider


def get_ocr_from_db(file_hash: str) -> dict | None:
    return get_storage_provider().get_ocr_cache(file_hash)


def save_ocr_to_db(
    file_hash: str,
    filename: str,
    ocr_text: str,
    model_name: str = "unknown",
    layout_json: str | None = None,
) -> None:
    get_storage_provider().save_ocr_cache(
        file_hash, ocr_text, filename, model_name, layout_json
    )


def save_figure_to_db(
    paper_id: str,
    page_number: int,
    bbox: list | tuple,
    image_url: str,
    caption: str = "",
    explanation: str = "",
    label: str = "figure",
    latex: str = "",
) -> str:
    return get_storage_provider().save_figure(
        paper_id, page_number, bbox, image_url, caption, explanation, label, latex
    )
