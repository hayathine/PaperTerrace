from src.providers import get_storage_provider


def get_ocr_from_db(file_hash: str) -> str | None:
    return get_storage_provider().get_ocr_cache(file_hash)


def save_ocr_to_db(
    file_hash: str,
    filename: str,
    ocr_text: str,
    model_name: str = "unknown",
) -> None:
    get_storage_provider().save_ocr_cache(file_hash, ocr_text, filename, model_name)
