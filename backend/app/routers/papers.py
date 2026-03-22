"""
Papers Router
Handles paper management (list, get, delete, claim).
"""

from fastapi import APIRouter
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import CurrentUser, OptionalUser
from app.providers import get_storage_provider
from common.logger import ServiceLogger

log = ServiceLogger("Papers")

router = APIRouter(tags=["Papers"])


class ClaimPaperRequest(BaseModel):
    """ゲストとしてアップロードした論文をサインイン後にDBに保存するためのリクエスト。"""

    paper_id: str
    file_hash: str
    filename: str
    ocr_text: str = ""
    layout_json: str | None = None


@router.post("/papers/claim")
async def claim_paper(body: ClaimPaperRequest, user: CurrentUser):
    """
    ゲストとしてアップロードした論文をサインイン後にライブラリに保存する。

    フロントエンドの IndexedDB に保持されているデータを受け取り、
    認証済みユーザーの owner_id を付けて DB に保存する。
    """
    storage = get_storage_provider()
    storage.save_paper(
        paper_id=body.paper_id,
        file_hash=body.file_hash,
        filename=body.filename,
        ocr_text=body.ocr_text,
        html_content="",
        target_language="ja",
        layout_json=body.layout_json,
        owner_id=user.uid,
    )
    log.info(
        "claim_paper",
        "ゲスト論文をライブラリに保存しました",
        paper_id=body.paper_id,
        uid=user.uid,
    )
    return JSONResponse({"claimed": True, "paper_id": body.paper_id})


@router.get("/papers")
async def list_papers(user: OptionalUser = None, limit: int = 50):
    """
    List papers for the current user.

    [ゲストポリシー]
    ゲストユーザーはペーパーをDBに保存しないため、空リストを返す (HTTP 200)。
    チャット等のゲストセッションは別途 Redis で管理されており、
    エンドポイントごとのアクセス設計は以下の通り:
    - GET /papers      : ゲスト → 空リスト (保存ペーパーなし)
    - POST /chat       : ゲスト → セッションベースで許可 (Redis TTL 1h)
    - DELETE /papers/* : ゲスト → 401 (オーナー検証が必要)
    """
    if not user:
        return JSONResponse({"papers": []})

    storage = get_storage_provider()
    papers, _ = storage.get_user_papers(user.uid, page=1, per_page=limit)
    return JSONResponse({"papers": jsonable_encoder(papers)})


@router.get("/papers/{paper_id}")
async def get_paper(paper_id: str, user: OptionalUser = None):
    """
    Get a paper by ID.
    Performs ownership/visibility check.
    """
    storage = get_storage_provider()
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

    storage = get_storage_provider()
    paper = storage.get_paper(paper_id)
    if not paper:
        return JSONResponse({"error": "Paper not found"}, status_code=404)

    if paper.get("owner_id") != user.uid:
        return JSONResponse({"error": "Access denied"}, status_code=403)

    deleted = storage.delete_paper(paper_id)
    return JSONResponse({"deleted": deleted})
