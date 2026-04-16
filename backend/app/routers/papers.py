"""
Papers Router
Handles paper management (list, get, delete, claim, like).
"""

import asyncio

from fastapi import APIRouter, HTTPException, Query
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import CurrentUser, OptionalUser
from app.core.config import get_worker_api_url
from app.models.log_schemas.schemas import PaperLikeData
from app.providers import get_arq_pool, get_redis_client, get_storage_provider
from app.providers.pg_log import PgLogClient
from common.logger import ServiceLogger
from common.processing_status import get_analysis_needs

log = ServiceLogger("Papers")

router = APIRouter(tags=["Papers"])

# 一覧取得時に除外する重いフィールド（OCRテキスト・レイアウト・要約本文）
# 個別取得 GET /papers/{paper_id} では全フィールドを返す
_LIST_EXCLUDE_FIELDS = frozenset({
    "ocr_text",
    "html_content",
    "layout_json",
    "full_summary",
    "section_summary_json",
    "grobid_text",
})


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
    slim = [{k: v for k, v in p.items() if k not in _LIST_EXCLUDE_FIELDS} for p in papers]
    return JSONResponse({"papers": jsonable_encoder(slim)})


@router.get("/papers/{paper_id}")
async def get_paper(paper_id: str, user: OptionalUser = None):
    """
    Get a paper by ID.
    Performs ownership/visibility check.

    オーナーがアクセスした場合、未完了処理（summary/grobid/layout_status修復）を
    バックグラウンドで自動再トリガーする。
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

    # オーナーアクセス時: 未完了処理をバックグラウンドで自動修復
    # layout は重い処理のため include_layout=False（手動エンドポイントのみ）
    if is_owner and get_analysis_needs(paper).any:
        asyncio.create_task(
            _auto_heal_paper(paper, user_id=user.uid, storage=storage)
        )

    return JSONResponse(jsonable_encoder(paper))


async def _auto_heal_paper(paper: dict, user_id: str, storage) -> None:
    """GET アクセス時にバックグラウンドで未完了処理を修復する。

    layout 再解析（重い処理）は行わず、summary / grobid の再実行と
    layout_status のステータス修復のみを行う。
    """
    from app.domain.services.paper_reanalysis import trigger_pending_analyses  # noqa: PLC0415

    try:
        await trigger_pending_analyses(
            paper=paper,
            user_id=user_id,
            storage=storage,
            include_layout=False,
        )
    except Exception as e:
        log.warning(
            "_auto_heal_paper",
            "自動修復に失敗",
            paper_id=paper["paper_id"],
            error=str(e),
        )


@router.post("/papers/{paper_id}/reanalyze")
async def reanalyze_paper(paper_id: str, user: CurrentUser):
    """
    論文の未完了処理（layout / summary / grobid）を手動で再実行する。

    オーナーのみ実行可能。各ステータスが "success" / "skipped" でない場合のみ
    対応するタスクをトリガーする。layout_json が存在するが layout_status が
    未設定の場合はステータス修復のみ行う。
    """
    from app.domain.services.paper_reanalysis import trigger_pending_analyses  # noqa: PLC0415

    storage = get_storage_provider()
    paper = storage.get_paper(paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")

    if paper.get("owner_id") != user.uid:
        raise HTTPException(status_code=403, detail="Access denied")

    # "processing" 状態の項目は手動再実行では強制リセットして再トリガーできるようにする
    for field in ("layout_status", "summary_status", "grobid_status"):
        if paper.get(field) == "processing":
            try:
                storage.update_processing_status(paper_id, field, None)
            except Exception as e:
                log.warning(
                    "reanalyze_paper",
                    f"{field} のリセットに失敗",
                    paper_id=paper_id,
                    error=str(e),
                )
    # リセット後の最新状態を取得
    paper = storage.get_paper(paper_id) or paper

    needs = get_analysis_needs(paper)
    if not needs.any:
        return JSONResponse({"triggered": {}, "message": "全ての処理が完了済みです"})

    worker_api_url = get_worker_api_url()
    arq_pool = await get_arq_pool()
    sync_redis = get_redis_client()

    triggered = await trigger_pending_analyses(
        paper=paper,
        user_id=user.uid,
        storage=storage,
        worker_api_url=worker_api_url,
        arq_pool=arq_pool,
        sync_redis=sync_redis,
        include_layout=True,
    )

    log.info(
        "reanalyze_paper",
        "再解析トリガー完了",
        paper_id=paper_id,
        triggered=triggered,
        uid=user.uid,
    )
    return JSONResponse({"triggered": triggered})


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
    logs PostgreSQL にイベントログを記録し、Neon の like_count をインクリメントする。
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
    logs PostgreSQL にイベントログを記録し、Neon の like_count をデクリメントする。
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
