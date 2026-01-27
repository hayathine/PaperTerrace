"""
Explore API router.
Handles public paper discovery and search.
"""

from fastapi import APIRouter, Query

from src.logger import logger
from src.models import PaperListResponse, PaperPublic
from src.providers import get_storage_provider

router = APIRouter(prefix="/explore", tags=["Explore"])


@router.get("", response_model=PaperListResponse)
async def explore_papers(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    sort: str = Query("recent", pattern="^(recent|popular|trending)$"),
):
    """
    Get public papers for exploration.

    Sort options:
    - recent: Most recently uploaded
    - popular: Most viewed
    - trending: Most liked in the past week
    """
    storage = get_storage_provider()

    try:
        papers, total = storage.get_public_papers(
            page=page,
            per_page=per_page,
            sort=sort,
        )

        paper_list = []
        for paper in papers:
            # Get owner info
            owner_data = None
            if paper.get("owner_id"):
                owner_data = storage.get_user(paper["owner_id"])

            paper_list.append(
                PaperPublic(
                    id=paper["id"],
                    title=paper["title"],
                    authors=paper.get("authors"),
                    abstract=paper.get("abstract"),
                    tags=paper.get("tags", []),
                    visibility=paper.get("visibility", "public"),
                    view_count=paper.get("view_count", 0),
                    like_count=paper.get("like_count", 0),
                    created_at=paper["created_at"],
                    owner_id=paper.get("owner_id"),
                    owner_name=owner_data.get("display_name") if owner_data else None,
                    owner_image_url=owner_data.get("profile_image_url") if owner_data else None,
                )
            )

        logger.info(
            "Explore papers retrieved",
            extra={"count": len(paper_list), "total": total, "sort": sort},
        )

        return PaperListResponse(
            papers=paper_list,
            total=total,
            page=page,
            per_page=per_page,
            has_more=page * per_page < total,
        )
    except Exception as e:
        logger.exception("Failed to get explore papers", extra={"error": str(e)})
        return PaperListResponse(
            papers=[],
            total=0,
            page=page,
            per_page=per_page,
            has_more=False,
        )


@router.get("/search", response_model=PaperListResponse)
async def search_papers(
    q: str = Query(..., min_length=1, max_length=200, description="検索クエリ"),
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
):
    """
    Search public papers by title, authors, or abstract.
    """
    storage = get_storage_provider()

    try:
        papers, total = storage.search_public_papers(
            query=q,
            page=page,
            per_page=per_page,
        )

        paper_list = []
        for paper in papers:
            owner_data = None
            if paper.get("owner_id"):
                owner_data = storage.get_user(paper["owner_id"])

            paper_list.append(
                PaperPublic(
                    id=paper["id"],
                    title=paper["title"],
                    authors=paper.get("authors"),
                    abstract=paper.get("abstract"),
                    tags=paper.get("tags", []),
                    visibility=paper.get("visibility", "public"),
                    view_count=paper.get("view_count", 0),
                    like_count=paper.get("like_count", 0),
                    created_at=paper["created_at"],
                    owner_id=paper.get("owner_id"),
                    owner_name=owner_data.get("display_name") if owner_data else None,
                    owner_image_url=owner_data.get("profile_image_url") if owner_data else None,
                )
            )

        logger.info(
            "Paper search completed",
            extra={"query": q, "count": len(paper_list), "total": total},
        )

        return PaperListResponse(
            papers=paper_list,
            total=total,
            page=page,
            per_page=per_page,
            has_more=page * per_page < total,
        )
    except Exception as e:
        logger.exception("Paper search failed", extra={"query": q, "error": str(e)})
        return PaperListResponse(
            papers=[],
            total=0,
            page=page,
            per_page=per_page,
            has_more=False,
        )


@router.get("/tags")
async def get_popular_tags(limit: int = Query(20, ge=1, le=100)):
    """
    Get popular tags across all public papers.
    """
    storage = get_storage_provider()

    try:
        tags = storage.get_popular_tags(limit=limit)
        return {"tags": tags}
    except Exception as e:
        logger.exception("Failed to get popular tags", extra={"error": str(e)})
        return {"tags": []}
