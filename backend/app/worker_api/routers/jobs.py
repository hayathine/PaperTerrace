"""
ジョブ管理ルーター

POST   /jobs                 - レイアウト解析ジョブを投入
GET    /jobs/{job_id}        - ジョブのステータス・結果を取得
GET    /jobs/{job_id}/stream - SSE でジョブ完了を通知
"""

import asyncio
import json

from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from app.workers.layout_job import (
    JOB_PUB_PREFIX,
    enqueue_layout_job,
    get_job_status,
)
from common.logger import ServiceLogger

log = ServiceLogger("WorkerAPI.Jobs")

router = APIRouter(prefix="/jobs", tags=["Jobs"])

TIMEOUT = 125.0
HEARTBEAT_INTERVAL = 15.0


class JobRequest(BaseModel):
    """レイアウト解析ジョブ投入リクエスト。"""

    paper_id: str
    page_numbers: list[int] | None = None
    user_id: str | None = None
    file_hash: str | None = None
    session_id: str | None = None


def _get_deps():
    """Redis クライアントと ARQ pool を取得する。"""
    from app.worker_api.main import get_arq, get_redis

    redis_client = get_redis()
    arq_pool = get_arq()
    if redis_client is None or arq_pool is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")
    return redis_client, arq_pool


@router.post("")
async def create_job(req: JobRequest):
    """レイアウト解析ジョブをキューに投入し job_id を返す。"""
    redis_client, arq_pool = _get_deps()

    try:
        job_id = await enqueue_layout_job(
            arq_pool,
            redis_client,
            paper_id=req.paper_id,
            page_numbers=req.page_numbers,
            user_id=req.user_id,
            file_hash=req.file_hash,
            session_id=req.session_id,
        )
        log.info("create_job", "Job enqueued", job_id=job_id, paper_id=req.paper_id)
        return JSONResponse({"job_id": job_id, "status": "queued"})
    except Exception as e:
        log.error("create_job", "Failed to enqueue job", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to enqueue layout analysis job.")


@router.get("/{job_id}")
async def get_job(job_id: str):
    """ジョブのステータスと結果を返す。"""
    redis_client, _ = _get_deps()

    job = get_job_status(redis_client, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    status = job.get("status")
    if status == "completed":
        figures = job.get("result", [])
        return JSONResponse({
            "success": True,
            "job_id": job_id,
            "status": "completed",
            "figures_detected": len(figures),
            "figures": figures,
        })

    return JSONResponse({
        "success": True,
        "job_id": job_id,
        "status": status,
        "error": job.get("error"),
    })


@router.get("/{job_id}/stream")
async def stream_job(job_id: str):
    """SSE でジョブ完了を通知する。"""
    redis_client, _ = _get_deps()

    async def generate():
        deadline = asyncio.get_event_loop().time() + TIMEOUT
        last_heartbeat = asyncio.get_event_loop().time()

        # 既に完了・失敗していれば即返す
        job = get_job_status(redis_client, job_id)
        if job is None:
            yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
            return

        status = job.get("status")
        if status == "completed":
            figures = job.get("result", [])
            yield f"data: {json.dumps({'status': 'completed', 'figures': figures, 'figures_detected': len(figures)})}\n\n"
            return
        if status == "failed":
            yield f"data: {json.dumps({'status': 'failed', 'error': job.get('error')})}\n\n"
            return

        yield f"data: {json.dumps({'status': status})}\n\n"

        # Pub/Sub で完了を待つ（失敗時はポーリングにフォールバック）
        pubsub = None
        use_pubsub = False
        try:
            pubsub = redis_client.pubsub()
            await asyncio.to_thread(pubsub.subscribe, f"{JOB_PUB_PREFIX}{job_id}")
            use_pubsub = True
        except Exception as e:
            log.warning("stream_job", "Pub/Sub unavailable, falling back to polling", error=str(e))
            if pubsub:
                try:
                    await asyncio.to_thread(pubsub.unsubscribe)
                except Exception:
                    pass
                pubsub = None

        try:
            if use_pubsub:
                while asyncio.get_event_loop().time() < deadline:
                    now = asyncio.get_event_loop().time()
                    if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now

                    try:
                        message = await asyncio.to_thread(
                            pubsub.get_message, ignore_subscribe_messages=True, timeout=0.2
                        )
                    except Exception:
                        message = None

                    if message and message.get("type") == "message":
                        try:
                            data = json.loads(message["data"])
                            evt_status = data.get("status")
                            if evt_status == "partial":
                                figures = data.get("figures", [])
                                if not isinstance(figures, list):
                                    figures = []
                                yield f"data: {json.dumps({'status': 'partial', 'figures': figures})}\n\n"
                            elif evt_status == "completed":
                                figures = data.get("result", [])
                                if not isinstance(figures, list):
                                    figures = []
                                yield f"data: {json.dumps({'status': 'completed', 'figures': figures, 'figures_detected': len(figures)})}\n\n"
                                return
                            elif evt_status == "failed":
                                yield f"data: {json.dumps({'status': 'failed', 'error': data.get('error')})}\n\n"
                                return
                        except Exception:
                            pass
            else:
                # ポーリングフォールバック
                while asyncio.get_event_loop().time() < deadline:
                    now = asyncio.get_event_loop().time()
                    if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now

                    job = get_job_status(redis_client, job_id)
                    if job is None:
                        yield f"data: {json.dumps({'status': 'not_found'})}\n\n"
                        return

                    status = job.get("status")
                    if status == "completed":
                        figures = job.get("result", [])
                        yield f"data: {json.dumps({'status': 'completed', 'figures': figures, 'figures_detected': len(figures)})}\n\n"
                        return
                    if status == "failed":
                        yield f"data: {json.dumps({'status': 'failed', 'error': job.get('error')})}\n\n"
                        return

                    yield f"data: {json.dumps({'status': status})}\n\n"
                    # processing 中は短いインターバル、queued 等の待機中は長め
                    await asyncio.sleep(0.3 if status == "processing" else 1.0)

        finally:
            if pubsub:
                try:
                    await asyncio.to_thread(pubsub.unsubscribe)
                    await asyncio.to_thread(pubsub.close)
                except Exception:
                    pass

        yield f"data: {json.dumps({'status': 'timeout'})}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )
