from common.logger import logger
from common.utils.crypto import get_file_hash


def _get_file_hash(file_bytes: bytes) -> str:
    """PDFなどのバイナリデータからSHA256ハッシュを計算する。"""
    return get_file_hash(file_bytes)


def log_gemini_token_usage(response, label: str = "Gemini Call"):
    """
    Gemini APIのレスポンスから使用トークン数をログ出力する共通関数。

    Args:
        response: genai의 레スポンスオブジェクト
        label: ログに出力するラベル（例: "ContextTrans", "OCR"）
    """
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        logger.info(
            f"Gemini Token Usage ({label}): "
            f"input={response.usage_metadata.prompt_token_count}, "
            f"output={response.usage_metadata.candidates_token_count}"
        )


async def fetch_image_bytes_from_url(url: str) -> bytes | None:
    """Fetch image bytes from a local static URL or HTTP URL."""
    import os

    import httpx

    try:
        if url.startswith("/static/"):
            # Local file mapped to src/static/...
            # Assuming CWD is project root, and url matches src structure
            # url: /static/paper_images/... -> src/static/paper_images/...
            relative_path = url.lstrip("/")
            file_path = f"src/{relative_path}"

            # Sanity check path
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    return f.read()
        elif url.startswith("http"):
            async with httpx.AsyncClient() as client:
                resp = await client.get(url, follow_redirects=True, timeout=10.0)
                if resp.status_code == 200:
                    return resp.content
    except Exception as e:
        logger.error(f"Failed to fetch image from {url}: {e}")
    return None
