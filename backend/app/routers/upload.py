"""
Upload Router
Handles file uploads (e.g. images for notes).
"""

import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from common.logger import ServiceLogger

# 許可する画像ファイルの拡張子ホワイトリスト
_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "gif", "webp"}

# 画像ファイルのマジックバイトシグネチャ
_MAGIC_SIGNATURES: list[tuple[bytes, str]] = [
    (b"\xff\xd8\xff", "jpeg"),
    (b"\x89PNG\r\n\x1a\n", "png"),
    (b"GIF87a", "gif"),
    (b"GIF89a", "gif"),
    (b"RIFF", "webp"),  # RIFF????WEBP (4バイト目からファイルサイズが入るため先頭4バイトのみ)
]

_MAX_UPLOAD_IMAGE_BYTES = 10 * 1024 * 1024  # 10MB


def _is_valid_image_magic(data: bytes) -> bool:
    """マジックバイトで画像ファイルかどうかを検証する。"""
    for sig, _ in _MAGIC_SIGNATURES:
        if data[:len(sig)] == sig:
            return True
    return False

log = ServiceLogger("Upload")


router = APIRouter(tags=["Upload"])

UPLOAD_DIR = Path("src/static/user_uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/upload/image")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload an image file.
    Returns the URL of the uploaded image.
    """
    try:
        if not file.content_type or not file.content_type.startswith("image/"):
            return JSONResponse(
                {"error": "Invalid file type. Only images are allowed."},
                status_code=400,
            )

        # 拡張子ホワイトリスト検証
        ext = file.filename.rsplit(".", 1)[-1].lower() if file.filename and "." in file.filename else ""
        if ext not in _ALLOWED_EXTENSIONS:
            return JSONResponse(
                {"error": f"Unsupported file extension. Allowed: {', '.join(sorted(_ALLOWED_EXTENSIONS))}"},
                status_code=400,
            )

        # ファイル内容を読み込んでサイズとマジックバイトを検証
        content = await file.read()
        if len(content) > _MAX_UPLOAD_IMAGE_BYTES:
            return JSONResponse(
                {"error": f"File size exceeds {_MAX_UPLOAD_IMAGE_BYTES // (1024 * 1024)}MB limit."},
                status_code=400,
            )
        if not _is_valid_image_magic(content):
            return JSONResponse(
                {"error": "File content does not match an allowed image format."},
                status_code=400,
            )

        # Generate unique filename
        safe_ext = ext if ext in _ALLOWED_EXTENSIONS else "jpg"
        filename = f"{uuid.uuid4()}_{int(time.time())}.{safe_ext}"
        file_path = UPLOAD_DIR / filename

        # Save file
        with file_path.open("wb") as buffer:
            buffer.write(content)

        file_url = f"/static/user_uploads/{filename}"
        log.info("upload_image", "Image uploaded", file_url=file_url)

        return JSONResponse({"url": file_url})
    except Exception as e:
        log.error("upload_image", "Failed to upload image", error=str(e))

        return JSONResponse({"error": "Failed to upload image"}, status_code=500)
