"""
Papers Router
Handles paper management (list, get, delete).
"""

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse

from app.auth import OptionalUser
from app.providers import get_storage_provider

router = APIRouter(tags=["Papers"])

# Services
storage = get_storage_provider()


@router.get("/papers")
async def list_papers(user: OptionalUser = None, limit: int = 50):
    """
    List papers for the current user.
    If not logged in, returns an empty list (as guest papers are not saved).
    """
    if not user:
        return JSONResponse({"papers": []})

    # Get papers owned by this user
    papers, _ = storage.get_user_papers(user.uid, page=1, per_page=limit)
    return JSONResponse({"papers": jsonable_encoder(papers)})


@router.get("/papers/{paper_id}")
async def get_paper(paper_id: str, user: OptionalUser = None):
    """
    Get a paper by ID.
    Performs ownership/visibility check.
    """
    paper = storage.get_paper(paper_id)
    if not paper:
        return JSONResponse({"error": "Paper not found"}, status_code=404)

    # Ownership/Visibility check
    is_owner = user and paper.get("owner_id") == user.uid
    is_public = paper.get("visibility") == "public"

    if not is_owner and not is_public:
        # If guest and paper is not public, or logged in as other user
        # Note: If it's a guest paper (owner_id is None), it's not visible via this endpoint
        # unless it was marked public (which currently guests can't do).
        return JSONResponse(
            {"error": "Access denied / アクセス権限がありません"}, status_code=403
        )

    return JSONResponse(jsonable_encoder(paper))


@router.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str, user: OptionalUser = None):
    """Delete a paper by ID. Only the owner can delete."""
    if not user:
        return JSONResponse({"error": "Authentication required"}, status_code=401)

    paper = storage.get_paper(paper_id)
    if not paper:
        return JSONResponse({"error": "Paper not found"}, status_code=404)

    if paper.get("owner_id") != user.uid:
        return JSONResponse({"error": "Access denied"}, status_code=403)

    deleted = storage.delete_paper(paper_id)
    return JSONResponse({"deleted": deleted})
