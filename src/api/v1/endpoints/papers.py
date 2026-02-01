"""
Papers Router
Handles paper management (list, get, delete).
"""

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from src.core.logger import logger
from src.infra import get_storage_provider

router = APIRouter(tags=["Papers"])

# Services
storage = get_storage_provider()


@router.get("/papers")
async def list_papers(limit: int = 50):
    try:
        logger.info(f"[Papers] Listing papers with limit {limit}")
        papers = storage.list_papers(limit)
        return JSONResponse({"papers": jsonable_encoder(papers)})
    except Exception:
        logger.exception("[Papers] Failed to list papers")
        return JSONResponse({"error": "Failed to list papers"}, status_code=500)


@router.get("/papers/{paper_id}")
async def get_paper(paper_id: str):
    try:
        logger.info(f"[Papers] Getting paper {paper_id}")
        paper = storage.get_paper(paper_id)
        if not paper:
            logger.warning(f"[Papers] Paper not found: {paper_id}")
            return JSONResponse({"error": "Paper not found"}, status_code=404)
        return JSONResponse(jsonable_encoder(paper))
    except Exception:
        logger.exception(f"[Papers] Failed to get paper {paper_id}")
        return JSONResponse({"error": "Internal server error"}, status_code=500)


@router.get("/papers/{paper_id}")
@router.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str):
    try:
        logger.info(f"[Papers] Deleting paper {paper_id}")
        deleted = storage.delete_paper(paper_id)
        return JSONResponse({"deleted": deleted})
    except Exception:
        logger.exception(f"[Papers] Failed to delete paper {paper_id}")
        return JSONResponse({"error": "Failed to delete paper"}, status_code=500)
