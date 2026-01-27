"""
Authentication API router.
Handles user registration and profile management.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from src.auth import CurrentUser
from src.logger import logger
from src.models import UserInDB, UserStats, UserUpdate
from src.providers import get_storage_provider

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", response_model=UserInDB, status_code=status.HTTP_201_CREATED)
async def register_user(
    user: CurrentUser,
):
    """
    Register a new user or return existing user.

    Called after Firebase authentication to create/update local user record.
    """
    storage = get_storage_provider()

    # Check if user already exists
    existing_user = storage.get_user(user.uid)
    if existing_user:
        logger.info("User already registered", extra={"uid": user.uid})
        return UserInDB(**existing_user)

    # Create new user
    now = datetime.now()
    user_data = {
        "id": user.uid,
        "email": user.email,
        "display_name": user.name or user.email.split("@")[0],
        "affiliation": None,
        "bio": None,
        "research_fields": [],
        "profile_image_url": user.picture,
        "is_public": True,
        "created_at": now,
        "updated_at": now,
    }

    try:
        storage.create_user(user_data)
        logger.info(
            "User registered",
            extra={"uid": user.uid, "email": user.email, "provider": user.provider},
        )
        return UserInDB(**user_data)
    except Exception as e:
        logger.exception("Failed to register user", extra={"uid": user.uid, "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="ユーザー登録に失敗しました",
        ) from e


@router.get("/me", response_model=UserInDB)
async def get_current_user_profile(user: CurrentUser):
    """Get the current authenticated user's profile."""
    storage = get_storage_provider()

    user_data = storage.get_user(user.uid)
    if not user_data:
        # Auto-register if not found
        return await register_user(user)

    return UserInDB(**user_data)


@router.put("/me", response_model=UserInDB)
async def update_current_user_profile(
    update_data: UserUpdate,
    user: CurrentUser,
):
    """Update the current user's profile."""
    storage = get_storage_provider()

    user_data = storage.get_user(user.uid)
    if not user_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザーが見つかりません",
        )

    # Apply updates
    update_dict = update_data.model_dump(exclude_unset=True)
    update_dict["updated_at"] = datetime.now()

    try:
        storage.update_user(user.uid, update_dict)
        updated_user = storage.get_user(user.uid)
        logger.info("User profile updated", extra={"uid": user.uid})
        return UserInDB(**updated_user)
    except Exception as e:
        logger.exception("Failed to update user", extra={"uid": user.uid, "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="プロフィールの更新に失敗しました",
        ) from e


@router.get("/me/stats", response_model=UserStats)
async def get_current_user_stats(user: CurrentUser):
    """Get statistics for the current user."""
    storage = get_storage_provider()

    try:
        stats = storage.get_user_stats(user.uid)
        return UserStats(**stats)
    except Exception as e:
        logger.exception("Failed to get user stats", extra={"uid": user.uid, "error": str(e)})
        return UserStats()


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_current_user(user: CurrentUser):
    """
    Delete the current user's account.

    This does not delete the Firebase account, only the local profile.
    Papers owned by this user will be marked as orphaned.
    """
    storage = get_storage_provider()

    try:
        storage.delete_user(user.uid)
        logger.info("User deleted", extra={"uid": user.uid})
    except Exception as e:
        logger.exception("Failed to delete user", extra={"uid": user.uid, "error": str(e)})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="アカウント削除に失敗しました",
        ) from e
