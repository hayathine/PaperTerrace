"""
Note Router
Handles sidebar note functionality.
"""

from fastapi import APIRouter, Form
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import OptionalUser
from app.domain.features import SidebarNoteService
from app.providers import get_storage_provider

router = APIRouter(tags=["Notes"])

sidebar_note_service = SidebarNoteService()
# paper_id の解決にのみ使用 (ノートの読み書きは sidebar_note_service に委譲)
_storage = get_storage_provider()


class NoteRequest(BaseModel):
    session_id: str
    term: str
    note: str
    image_url: str | None = None
    page_number: int | None = None
    x: float | None = None
    y: float | None = None
    paper_id: str | None = None


@router.get("/note/{session_id}")
async def get_notes(session_id: str, user: OptionalUser, paper_id: str | None = None):
    user_id = user.uid if user else None

    # Resolve paper_id if not provided
    if not paper_id:
        paper_id = _storage.get_session_paper_id(session_id)

    notes = sidebar_note_service.get_notes(
        session_id, paper_id=paper_id, user_id=user_id
    )
    return JSONResponse({"notes": jsonable_encoder(notes)})


@router.post("/note")
async def add_note(request: NoteRequest, user: OptionalUser):
    user_id = user.uid if user else None

    # Resolve paper_id if not provided
    paper_id = request.paper_id
    if not paper_id:
        paper_id = _storage.get_session_paper_id(request.session_id)

    note = sidebar_note_service.add_note(
        request.session_id,
        request.term,
        request.note,
        request.image_url,
        request.page_number,
        request.x,
        request.y,
        user_id=user_id,
        paper_id=paper_id,
    )
    return JSONResponse(jsonable_encoder(note))


@router.put("/note/{note_id}")
async def update_note(note_id: str, request: NoteRequest, user: OptionalUser = None):
    user_id = user.uid if user else None
    # We reuse the add_note logic or storage save logic which handles upsert
    # But usually we want a specific update method in service.
    # For now, let's assume upsert or create a new service method.
    # checking sidebar_note_service... it just calls storage.save_note
    try:
        updated = sidebar_note_service.add_note(
            request.session_id,
            request.term,
            request.note,
            request.image_url,
            request.page_number,
            request.x,
            request.y,
            user_id=user_id,
            note_id=note_id,  # We need to pass note_id to update specific note
            paper_id=request.paper_id,
        )
        return JSONResponse(jsonable_encoder(updated))
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@router.delete("/note/{note_id}")
async def delete_note(note_id: str, user: OptionalUser, paper_id: str | None = None):
    user_id = user.uid if user else None
    deleted = sidebar_note_service.delete_note(note_id, user_id=user_id, paper_id=paper_id)
    return JSONResponse({"deleted": deleted})


@router.post("/note/export")
async def export_notes(session_id: str = Form(...)):
    export_text = sidebar_note_service.export_notes(session_id)
    return JSONResponse({"export": export_text})
