"""
Papers Router
Handles paper management (list, get, delete, claim, like).
"""

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import CurrentUser, OptionalUser
from app.models.bigquery.schemas import PaperLikeData
from app.providers import get_storage_provider
from app.providers.pg_log import PgLogClient
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
async def list_papers(user: OptionalUser = None, limit: int = Query(default=50, ge=1, le=100)):
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


@router.post("/papers/{paper_id}/like")
async def like_paper(paper_id: str, user: CurrentUser):
    """
    論文にいいねを付ける。
    BigQuery にイベントログを記録し、Neon の like_count をインクリメントする。
    """
    storage = get_storage_provider()
    paper = storage.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    try:
        pg = PgLogClient.get_instance()
        pg.insert("paper_likes", [PaperLikeData(user_id=user.uid, paper_id=paper_id, action="like").to_pg_row()])
    except Exception as e:
        log.warning("like_paper", "PG insert failed", error=str(e), paper_id=paper_id)

    storage.increment_like_count(paper_id)
    log.info("like_paper", "いいね完了", paper_id=paper_id, uid=user.uid)
    return JSONResponse({"ok": True})


@router.delete("/papers/{paper_id}/like")
async def unlike_paper(paper_id: str, user: CurrentUser):
    """
    論文のいいねを取り消す。
    BigQuery にイベントログを記録し、Neon の like_count をデクリメントする。
    """
    storage = get_storage_provider()
    paper = storage.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    try:
        pg = PgLogClient.get_instance()
        pg.insert("paper_likes", [PaperLikeData(user_id=user.uid, paper_id=paper_id, action="unlike").to_pg_row()])
    except Exception as e:
        log.warning("unlike_paper", "PG insert failed", error=str(e), paper_id=paper_id)

    storage.decrement_like_count(paper_id)
    log.info("unlike_paper", "いいね取り消し完了", paper_id=paper_id, uid=user.uid)
    return JSONResponse({"ok": True})
