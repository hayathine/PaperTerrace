"""
Upload Router
Handles file uploads (e.g. images for notes).
"""

import shutil
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, UploadFile
from fastapi.responses import JSONResponse

from app.logger import logger

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
        if not file.content_type.startswith("image/"):
            return JSONResponse(
                {"error": "Invalid file type. Only images are allowed."},
                status_code=400,
            )

        # Generate unique filename
        ext = file.filename.split(".")[-1] if "." in file.filename else "png"
        filename = f"{uuid.uuid4()}_{int(time.time())}.{ext}"
        file_path = UPLOAD_DIR / filename

        # Save file
        with file_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        file_url = f"/static/user_uploads/{filename}"
        logger.info(f"Image uploaded: {file_url}")

        return JSONResponse({"url": file_url})
    except Exception as e:
        logger.error(f"Failed to upload image: {e}")
        return JSONResponse({"error": "Failed to upload image"}, status_code=500)
