"""
Authentication API router.
Handles user registration and profile management.
"""

from datetime import datetime

from fastapi import APIRouter, HTTPException, status

from app.auth import CurrentUser
from app.models.user import UserInDB, UserStats, UserUpdate
from app.providers import get_storage_provider
from common.logger import ServiceLogger

log = ServiceLogger("Auth")


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

    # Check if user already exists (by UID or email)
    existing_user = storage.get_user(user.uid)
    if not existing_user and user.email:
        existing_user = storage.get_user_by_email(user.email)
        if existing_user and existing_user.get("id") != user.uid:
            # 認証プロバイダー移行 (Firebase → Neon Auth) による UID 変更を検出。
            # DB の id を新しい UID に更新することで以降の処理を正常化する。
            old_uid = existing_user["id"]
            try:
                storage.migrate_user_uid(old_uid, user.uid)
                existing_user["id"] = user.uid
                log.warning(
                    "register",
                    "UID移行: 旧UIDを新UIDで上書きしました",
                    old_uid=old_uid,
                    new_uid=user.uid,
                    email=user.email,
                )
            except Exception as migrate_err:
                log.error(
                    "register",
                    "UID移行に失敗しました",
                    old_uid=old_uid,
                    new_uid=user.uid,
                    error=str(migrate_err),
                )
    if existing_user:
        log.info("register", "ユーザーは既に登録されています", uid=user.uid)
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
        log.info(
            "register",
            "ユーザーを登録しました",
            uid=user.uid,
            email=user.email,
            provider=user.provider,
        )
        return UserInDB(**user_data)

    except Exception as e:
        # レースコンディション（複数インスタンスの同時リクエスト等）による
        # UniqueViolation の場合は、既存ユーザーを返す
        error_str = str(e).lower()
        if "unique" in error_str or "duplicate" in error_str:
            log.warning(
                "register",
                "UniqueViolation: 既存ユーザーとして処理",
                uid=user.uid,
                email=user.email,
            )
            recovered = storage.get_user(user.uid) or (
                user.email and storage.get_user_by_email(user.email)
            )
            if recovered:
                return UserInDB(**recovered)

        log.exception("register", "ユーザー登録に失敗しました", uid=user.uid, error=str(e))
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
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ユーザープロファイルが見つかりません。ゲストとして実行中です。",
        )

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
        log.info("update_profile", "ユーザープロファイルを更新しました", uid=user.uid)
        return UserInDB(**updated_user)

    except Exception as e:
        log.exception(
            "update_profile", "ユーザーの更新に失敗しました", uid=user.uid, error=str(e)
        )

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
        log.exception("stats", "ユーザー統計の取得に失敗しました", uid=user.uid, error=str(e))
        return UserStats()


@router.get("/me/persona")
async def get_user_persona(user: CurrentUser):
    """ユーザーのペルソナプロファイルを返す。未生成の場合は空オブジェクト。"""
    storage = get_storage_provider()
    try:
        persona = storage.get_user_persona(user.uid)
        return persona or {}
    except Exception as e:
        log.exception("persona", "ペルソナの取得に失敗しました", uid=user.uid, error=str(e))
        return {}


@router.get("/me/translations")
async def get_user_translations(
    user: CurrentUser,
    page: int = 1,
    per_page: int = 20,
):
    """ユーザーの保存済み翻訳・解説履歴を返す。"""
    storage = get_storage_provider()

    try:
        notes, total = storage.get_user_translations(user.uid, page, per_page)
        return {
            "translations": [
                {
                    "term": n.term,
                    "note": n.note,
                    "paper_id": n.paper_id,
                    "page_number": n.page_number,
                    "created_at": n.created_at,
                }
                for n in notes
            ],
            "total": total,
            "page": page,
            "per_page": per_page,
        }
    except Exception as e:
        log.exception(
            "translations", "翻訳履歴の取得に失敗しました", uid=user.uid, error=str(e)
        )
        return {"translations": [], "total": 0, "page": page, "per_page": per_page}


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
        log.info("delete_account", "ユーザーを削除しました", uid=user.uid)
    except Exception as e:
        log.exception(
            "delete_account", "ユーザーの削除に失敗しました", uid=user.uid, error=str(e)
        )

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="アカウント削除に失敗しました",
        ) from e
