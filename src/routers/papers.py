"""
Papers Router
Handles paper management (list, get, delete).
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from ..providers import get_storage_provider

router = APIRouter(tags=["Papers"])

# Services
storage = get_storage_provider()


@router.get("/papers")
async def list_papers(limit: int = 50):
    papers = storage.list_papers(limit)
    return JSONResponse({"papers": papers})


@router.get("/papers/{paper_id}")
async def get_paper(paper_id: str):
    paper = storage.get_paper(paper_id)
    if not paper:
        return JSONResponse({"error": "Paper not found"}, status_code=404)
    return JSONResponse(paper)


@router.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str):
    deleted = storage.delete_paper(paper_id)
    return JSONResponse({"deleted": deleted})
