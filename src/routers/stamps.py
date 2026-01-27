"""
Stamps Router
Handles stamp functionality for Papers and Notes.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..providers import get_storage_provider

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
async def add_paper_stamp(paper_id: str, request: StampRequest):
    """Add a stamp to a paper."""
    stamp_id = storage.add_paper_stamp(
        paper_id,
        request.stamp_type,
        request.user_id,
        page_number=request.page_number,
        x=request.x,
        y=request.y,
    )
    return JSONResponse(
        {
            "stamp_id": stamp_id,
            "stamp_type": request.stamp_type,
            "page_number": request.page_number,
            "x": request.x,
            "y": request.y,
        }
    )


@router.get("/stamps/paper/{paper_id}")
async def get_paper_stamps(paper_id: str):
    """Get all stamps for a paper."""
    stamps = storage.get_paper_stamps(paper_id)
    return JSONResponse({"stamps": stamps})


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
    return JSONResponse({"stamps": stamps})


@router.delete("/stamps/note/{stamp_id}")
async def delete_note_stamp(stamp_id: str):
    """Delete a stamp from a note."""
    deleted = storage.delete_note_stamp(stamp_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Stamp not found")
    return JSONResponse({"deleted": True})
