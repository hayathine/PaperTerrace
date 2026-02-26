"""
Stamps Router
Handles stamp functionality for Papers and Notes.
"""

import io
import time
import uuid
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from PIL import Image
from pydantic import BaseModel

from app.auth import OptionalUser
from app.providers import get_storage_provider
from common.logger import get_service_logger

logger = get_service_logger("Stamps")

STAMPS_UPLOAD_DIR = Path("app/static/user_uploads/stamps")
STAMPS_UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(tags=["Stamps"])

# Services
storage = get_storage_provider()


class StampRequest(BaseModel):
    stamp_type: str
    user_id: str | None = None  # Optional user_id (for future auth integration)
    page_number: int | None = None
    x: float | None = None
    y: float | None = None


@router.post("/stamps/paper/{paper_id}")
async def add_paper_stamp(paper_id: str, request: StampRequest, user: OptionalUser):
    """Add a stamp to a paper."""
    user_id = user.uid if user else None

    # Check if user is registered
    is_registered = False
    if user_id:
        if storage.get_user(user_id):
            is_registered = True

    if is_registered:
        stamp_id = storage.add_paper_stamp(
            paper_id,
            request.stamp_type,
            user_id,
            page_number=request.page_number,
            x=request.x,
            y=request.y,
        )
        logger.info(f"Stamp {stamp_id} added persistently for user {user_id}")
    else:
        import uuid6

        stamp_id = f"guest-{uuid6.uuid7()}"
        logger.info(f"Stamp added for guest {user_id} (not saved to DB)")

    return JSONResponse(
        {
            "stamp_id": stamp_id,
            "stamp_type": request.stamp_type,
            "page_number": request.page_number,
            "x": request.x,
            "y": request.y,
            "user_id": user_id,
        }
    )


@router.get("/stamps/paper/{paper_id}")
async def get_paper_stamps(paper_id: str):
    """Get all stamps for a paper."""
    stamps = storage.get_paper_stamps(paper_id)
    return JSONResponse({"stamps": jsonable_encoder(stamps)})


@router.delete("/stamps/paper/{stamp_id}")
async def delete_paper_stamp(stamp_id: str):
    """Delete a stamp from a paper."""
    deleted = storage.delete_paper_stamp(stamp_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Stamp not found")
    return JSONResponse({"deleted": True})


@router.post("/stamps/note/{note_id}")
async def add_note_stamp(note_id: str, request: StampRequest):
    """Add a stamp to a note."""
    stamp_id = storage.add_note_stamp(
        note_id,
        request.stamp_type,
        request.user_id,
        x=request.x,
        y=request.y,
    )
    return JSONResponse(
        {
            "stamp_id": stamp_id,
            "stamp_type": request.stamp_type,
            "x": request.x,
            "y": request.y,
        }
    )


@router.get("/stamps/note/{note_id}")
async def get_note_stamps(note_id: str):
    """Get all stamps for a note."""
    stamps = storage.get_note_stamps(note_id)
    return JSONResponse({"stamps": jsonable_encoder(stamps)})


@router.delete("/stamps/note/{stamp_id}")
async def delete_note_stamp(stamp_id: str):
    """Delete a stamp from a note."""
    deleted = storage.delete_note_stamp(stamp_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Stamp not found")
    return JSONResponse({"deleted": True})


@router.post("/stamps/upload_custom")
async def upload_custom_stamp(file: UploadFile = File(...)):
    """Upload an image to be used as a custom stamp.
    Enforces a file size limit (e.g. 512KB) and resizes images to max 256x256.
    """
    try:
        if not file.content_type.startswith("image/"):
            return JSONResponse(
                {"error": "Invalid file type. Only images are allowed."},
                status_code=400,
            )

        # Read file content into memory to check size
        # Limit to 512KB for a single stamp to prevent abuse
        content = await file.read()
        if len(content) > 512 * 1024:
            return JSONResponse(
                {"error": "File size exceeds 512KB limit."},
                status_code=400,
            )

        try:
            image = Image.open(io.BytesIO(content))
        except Exception:
            return JSONResponse(
                {"error": "Invalid image file format."},
                status_code=400,
            )

        # Resize to max 256x256 while preserving aspect ratio
        max_size = (256, 256)
        image.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save as PNG
        ext = "png"
        filename = f"{uuid.uuid4()}_{int(time.time())}.{ext}"
        file_path = STAMPS_UPLOAD_DIR / filename

        image.save(file_path, format="PNG")
        file_url = f"/static/user_uploads/stamps/{filename}"

        logger.info(f"Custom stamp uploaded: {file_url}")
        return JSONResponse({"url": file_url})
    except Exception as e:
        logger.error(f"Failed to upload custom stamp: {e}")
        return JSONResponse({"error": "Failed to upload custom stamp"}, status_code=500)
