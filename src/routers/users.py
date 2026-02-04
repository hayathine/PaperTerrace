"""
Users API router.
Handles public user profile viewing.
"""

from fastapi import APIRouter, HTTPException, status

from src.logger import logger
from src.models.paper import PaperListResponse, PaperPublic
from src.models.user import UserPublic
from src.providers import get_storage_provider

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/{user_id}", response_model=UserPublic)
async def get_user_profile(user_id: str):
    """
    Get a user's public profile.

    Only returns public profile information.
    """
    storage = get_storage_provider()

    user_data = storage.get_user(user_id)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません",
        )

    # Check if profile is public
    if not user_data.get("is_public", True):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません",
        )

    # Get paper count
    stats = storage.get_user_stats(user_id)

    return UserPublic(
        id=user_data["id"],
        display_name=user_data.get("display_name"),
        affiliation=user_data.get("affiliation"),
        bio=user_data.get("bio"),
        research_fields=user_data.get("research_fields", []),
        profile_image_url=user_data.get("profile_image_url"),
        paper_count=stats.get("public_paper_count", 0),
        created_at=user_data["created_at"],
    )


@router.get("/{user_id}/papers", response_model=PaperListResponse)
async def get_user_papers(
    user_id: str,
    page: int = 1,
    per_page: int = 20,
):
    """
    Get a user's public papers.

    Only returns papers with visibility='public'.
    """
    storage = get_storage_provider()

    # Verify user exists
    user_data = storage.get_user(user_id)
    if not user_data or not user_data.get("is_public", True):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません",
        )

    try:
        papers, total = storage.get_user_public_papers(
            user_id=user_id,
            page=page,
            per_page=per_page,
        )

        paper_list = []
        for paper in papers:
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
                    owner_id=user_id,
                    owner_name=user_data.get("display_name"),
                    owner_image_url=user_data.get("profile_image_url"),
                )
            )

        return PaperListResponse(
            papers=paper_list,
            total=total,
            page=page,
            per_page=per_page,
            has_more=page * per_page < total,
        )
    except Exception as e:
        logger.exception(
            "Failed to get user papers",
            extra={"user_id": user_id, "error": str(e)},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="論文の取得に失敗しました",
        ) from e
