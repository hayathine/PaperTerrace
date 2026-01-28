"""
Note Router
Handles sidebar note functionality.
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..features import SidebarNoteService

router = APIRouter(tags=["Notes"])

# Services
sidebar_note_service = SidebarNoteService()


class NoteRequest(BaseModel):
    session_id: str
    term: str
    note: str
    image_url: str | None = None


@router.get("/note/{session_id}")
async def get_notes(session_id: str):
    notes = sidebar_note_service.get_notes(session_id)
    return JSONResponse({"notes": notes})


@router.post("/note")
async def add_note(request: NoteRequest):
    note = sidebar_note_service.add_note(
        request.session_id, request.term, request.note, request.image_url
    )
    return JSONResponse(note)


@router.delete("/note/{note_id}")
async def delete_note(note_id: str):
    deleted = sidebar_note_service.delete_note(note_id)
    return JSONResponse({"deleted": deleted})


@router.post("/note/export")
async def export_notes(session_id: str = Form(...)):
    export_text = sidebar_note_service.export_notes(session_id)
    return JSONResponse({"export": export_text})
