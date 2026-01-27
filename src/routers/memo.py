"""
Memo Router
Handles sidebar memo functionality.
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..feature import SidebarMemoService

router = APIRouter(tags=["Memos"])

# Services
sidebar_memo_service = SidebarMemoService()


class MemoRequest(BaseModel):
    session_id: str
    term: str
    note: str


@router.get("/memo/{session_id}")
async def get_memos(session_id: str):
    memos = sidebar_memo_service.get_memos(session_id)
    return JSONResponse({"memos": memos})


@router.post("/memo")
async def add_memo(request: MemoRequest):
    memo = sidebar_memo_service.add_memo(request.session_id, request.term, request.note)
    return JSONResponse(memo)


@router.delete("/memo/{memo_id}")
async def delete_memo(memo_id: str):
    deleted = sidebar_memo_service.delete_memo(memo_id)
    return JSONResponse({"deleted": deleted})


@router.post("/memo/export")
async def export_memos(session_id: str = Form(...)):
    export_text = sidebar_memo_service.export_memos(session_id)
    return JSONResponse({"export": export_text})
