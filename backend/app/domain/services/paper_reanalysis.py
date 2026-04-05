"""
論文処理の再解析サービス。

layout_status / summary_status / grobid_status が未完了（null / failed）の
論文に対して、必要な解析タスクを再トリガーする。

使用例:
    triggered = await trigger_pending_analyses(
        paper=paper_dict,
        user_id=user_id,
        session_id=session_id,
        storage=storage,
        worker_api_url=get_worker_api_url(),
        arq_pool=arq_pool,
        sync_redis=sync_redis,
    )
"""

import asyncio

from common.logger import ServiceLogger
from common.processing_status import get_analysis_needs

from app.domain.services.paper_processing import (
    process_grobid_enrichment_task,
    process_paper_summary_task,
)

log = ServiceLogger("PaperReanalysis")


async def trigger_pending_analyses(
    paper: dict,
    user_id: str | None = None,
    session_id: str | None = None,
    storage=None,
    worker_api_url: str | None = None,
    arq_pool=None,
    sync_redis=None,
    include_layout: bool = True,
) -> dict[str, bool | str]:
    """
    論文の未完了解析を検出し、必要なタスクを再トリガーする。

    Args:
        paper: storage.get_paper() が返す論文辞書。
        user_id: ジョブに渡すユーザー ID。
        session_id: ジョブに渡すセッション ID。
        storage: ORMStorageAdapter インスタンス（layout_status 修復用）。
        worker_api_url: Worker API URL（prod/staging 用）。未設定なら Redis 直接モード。
        arq_pool: ARQ 非同期コネクションプール（Redis 直接モード用）。
        sync_redis: 同期 Redis クライアント（Redis 直接モード用）。
        include_layout: True の場合、layout 再解析（ARQ ジョブ投入）も行う。
                        False の場合、layout_status 修復のみ（軽量処理）。

    Returns:
        各解析の実行結果を示す辞書。
        {
            "layout": False | "<job_id>",  # 再解析ジョブを投入した場合は job_id
            "layout_heal": bool,           # ステータス修復のみ実施した場合
            "summary": bool,
            "grobid": bool,
        }
    """
    paper_id: str = paper["paper_id"]
    file_hash: str | None = paper.get("file_hash")
    needs = get_analysis_needs(paper)

    result: dict[str, bool | str] = {
        "layout": False,
        "layout_heal": False,
        "summary": False,
        "grobid": False,
    }

    if not needs.any:
        log.debug(
            "trigger_pending",
            "全ての処理が完了済み。再解析不要。",
            paper_id=paper_id,
        )
        return result

    log.info(
        "trigger_pending",
        "未完了処理を検出",
        paper_id=paper_id,
        layout=needs.layout,
        layout_heal=needs.layout_heal,
        summary=needs.summary,
        grobid=needs.grobid,
    )

    # -----------------------------------------------------------------------
    # layout_heal: layout_json が存在するが layout_status が未設定の場合
    # → 実解析は不要。ステータスを "success" に修復するだけ。
    # -----------------------------------------------------------------------
    if needs.layout_heal and storage:
        try:
            storage.update_processing_status(paper_id, "layout_status", "success")
            result["layout_heal"] = True
            log.info("trigger_pending", "layout_status を success に修復", paper_id=paper_id)
        except Exception as e:
            log.warning(
                "trigger_pending",
                "layout_status 修復に失敗",
                paper_id=paper_id,
                error=str(e),
            )

    # -----------------------------------------------------------------------
    # layout: layout_json も存在しない場合 → ARQ ジョブ投入で実解析
    # -----------------------------------------------------------------------
    if needs.layout and include_layout:
        job_id = await _enqueue_layout_analysis(
            paper_id=paper_id,
            file_hash=file_hash,
            user_id=user_id,
            session_id=session_id,
            worker_api_url=worker_api_url,
            arq_pool=arq_pool,
            sync_redis=sync_redis,
        )
        if job_id:
            result["layout"] = job_id
            log.info(
                "trigger_pending",
                "layout 解析ジョブ投入",
                paper_id=paper_id,
                job_id=job_id,
            )

    # -----------------------------------------------------------------------
    # summary: summary_status が未完了 → asyncio バックグラウンドタスク
    # -----------------------------------------------------------------------
    if needs.summary:
        asyncio.create_task(
            process_paper_summary_task(
                paper_id,
                user_id=user_id,
                session_id=session_id,
            )
        )
        result["summary"] = True
        log.info("trigger_pending", "summary タスク起動", paper_id=paper_id)

    # -----------------------------------------------------------------------
    # grobid: grobid_status が未完了 → asyncio バックグラウンドタスク
    # -----------------------------------------------------------------------
    if needs.grobid and file_hash:
        asyncio.create_task(
            process_grobid_enrichment_task(paper_id, file_hash)
        )
        result["grobid"] = True
        log.info("trigger_pending", "grobid タスク起動", paper_id=paper_id)

    return result


async def _enqueue_layout_analysis(
    paper_id: str,
    file_hash: str | None,
    user_id: str | None,
    session_id: str | None,
    worker_api_url: str | None,
    arq_pool,
    sync_redis,
) -> str | None:
    """レイアウト解析ジョブを投入し job_id を返す。投入失敗時は None を返す。"""

    # Worker API モード（prod / staging）
    if worker_api_url:
        try:
            import httpx  # noqa: PLC0415

            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.post(
                    f"{worker_api_url}/jobs",
                    json={
                        "paper_id": paper_id,
                        "page_numbers": None,
                        "user_id": user_id,
                        "file_hash": file_hash,
                        "session_id": session_id,
                    },
                )
                resp.raise_for_status()
                return resp.json().get("job_id")
        except Exception as e:
            log.error(
                "_enqueue_layout",
                "Worker API 経由でのジョブ投入に失敗",
                paper_id=paper_id,
                error=str(e),
            )
            return None

    # Redis 直接モード（ローカル開発）
    if arq_pool and sync_redis:
        try:
            from app.workers.layout_job import enqueue_layout_job  # noqa: PLC0415

            return await enqueue_layout_job(
                arq_pool,
                sync_redis,
                paper_id=paper_id,
                page_numbers=None,
                user_id=user_id,
                file_hash=file_hash,
                session_id=session_id,
            )
        except Exception as e:
            log.error(
                "_enqueue_layout",
                "ARQ キューへのジョブ投入に失敗",
                paper_id=paper_id,
                error=str(e),
            )
            return None

    log.warning(
        "_enqueue_layout",
        "Worker API も ARQ も利用不可のため layout 再解析をスキップ",
        paper_id=paper_id,
    )
    return None
