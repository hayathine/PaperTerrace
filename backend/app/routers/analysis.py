"""
Analysis Router
Handles paper analysis features: summary,
figure/table analysis, layout detection, and adversarial review.
"""

import asyncio
import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse, StreamingResponse

from app.auth import OptionalUser
from app.domain.features import (
    AdversarialReviewService,
    FigureInsightService,
    SummaryService,
)
from app.domain.services.layout_analysis_service import LayoutAnalysisService
from app.providers import (
    RedisService,
    get_arq_pool,
    get_redis_client,
    get_storage_provider,
)  # RedisService now uses in-memory cache
from app.workers.layout_job import enqueue_layout_job, get_job_status
from common.logger import ServiceLogger

log = ServiceLogger("Analysis")


router = APIRouter(tags=["Analysis"])

# Services
summary_service = SummaryService()
figure_insight_service = FigureInsightService()
adversarial_service = AdversarialReviewService()
redis_service = RedisService()


def _get_context(session_id: str) -> tuple[str | None, str | None]:
    """(context, paper_id) のタプルを返す。paper_id は取得できた場合のみ。"""
    # 1. Redis キャッシュを優先
    context = redis_service.get(f"session:{session_id}")
    if context:
        log.debug("get_context", "Cache HIT", session_id=session_id)
        redis_service.expire(f"session:{session_id}", 3600)
        # paper_id も別キーでキャッシュしている場合は返す
        paper_id = redis_service.get(f"session_pid:{session_id}")
        return context, paper_id

    # 2. DB から取得（キャッシュミス時）
    storage = get_storage_provider()
    paper_id = storage.get_session_paper_id(session_id)
    resolved_paper_id = paper_id or session_id

    paper = storage.get_paper(resolved_paper_id)
    if paper and paper.get("ocr_text"):
        log.debug("get_context", "Fetched FULL context from DB", paper_id=resolved_paper_id)
        # 次回のために paper_id をキャッシュ
        if paper_id:
            redis_service.set(f"session_pid:{session_id}", paper_id, expire=3600)
        return paper["ocr_text"], resolved_paper_id

    return None, None


# ============================================================================
# Summary
# ============================================================================


@router.post("/summarize")
async def summarize(
    session_id: str = Form(...),
    mode: str = Form("full"),
    lang: str = Form("ja"),
    paper_id: str | None = Form(None),
    key_word: str | None = Form(None),
    force: bool = Form(False),
    user: OptionalUser = None,
):
    context, resolved_paper_id = _get_context(session_id)
    if not context:
        log.warning("summarize", "Context not found", session_id=session_id)

        return JSONResponse(
            {"error": f"論文が読み込まれていません (session_id: {session_id})"},
            status_code=400,
        )

    try:
        storage = get_storage_provider()
        # Resolve paper_id if missing（DBアクセスは _get_context で取得済みの場合は不要）
        if not paper_id:
            paper_id = resolved_paper_id or storage.get_session_paper_id(session_id)

        # Clear cached summary if force=True
        if force and paper_id:
            log.info("summarize", "Force regeneration requested", paper_id=paper_id)
            storage.update_paper_full_summary(paper_id, "")
    except Exception as e:
        log.error("summarize", "Storage error during summarize setup", error=str(e))
        return JSONResponse(
            {"error": "ストレージへのアクセスに失敗しました。"},
            status_code=500,
        )

    log.info(
        "summarize",
        "Summarize request started",
        session_id=session_id,
        paper_id=paper_id,
        context_len=len(context),
        force=force,
    )

    current_user_id = user.uid if user else f"guest:{session_id}"

    summary, trace_id = await summary_service.summarize_full(
        context,
        target_lang=lang,
        paper_id=paper_id,
        user_id=current_user_id,
        session_id=session_id,
        key_word=key_word,
    )
    return JSONResponse({"summary": summary, "trace_id": trace_id})


# ============================================================================
# Figure Insight
# ============================================================================


@router.post("/analyze-figure")
async def analyze_figure(
    file: UploadFile = File(...),
    caption: str = Form(""),
    session_id: str | None = Form(None),
    paper_id: str | None = Form(None),
    user: OptionalUser = None,
):
    content = await file.read()
    mime_type = file.content_type or "image/jpeg"
    # Determine current user ID
    current_user_id = (
        user.uid if user else (f"guest:{session_id}" if session_id else None)
    )

    analysis = await figure_insight_service.analyze_figure(
        content,
        caption,
        mime_type,
        user_id=current_user_id,
        session_id=session_id,
        paper_id=paper_id,
    )
    return JSONResponse({"analysis": analysis})


# ============================================================================
# Adversarial Review
# ============================================================================


@router.post("/critique")
async def critique(
    session_id: str = Form(...), lang: str = Form("ja"), user: OptionalUser = None
):
    context, _ = _get_context(session_id)
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    current_user_id = user.uid if user else f"guest:{session_id}"
    critique = await adversarial_service.critique(
        context, target_lang=lang, user_id=current_user_id, session_id=session_id
    )
    return JSONResponse(critique)


# ============================================================================
# Layout Detection
# ============================================================================


@router.post("/analyze-layout-lazy")
async def analyze_layout_lazy(
    paper_id: str = Form(...),
    page_numbers: str | None = Form(None),
    file_hash: str | None = Form(None),
    session_id: str | None = Form(None),
    user: OptionalUser = None,
):
    """
    レイアウト解析ジョブをキューに投入し、job_id を即時返却する。
    結果は GET /layout-jobs/{job_id} でポーリングして取得する。
    """
    log.info(
        "layout_lazy",
        "Received lazy layout analysis request",
        paper_id=paper_id,
        pages=page_numbers,
    )

    # Parse page numbers
    parsed_pages = None
    if page_numbers:
        try:
            parsed_pages = [int(p.strip()) for p in page_numbers.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=400, detail="Invalid page_numbers format"
            )

    current_user_id = (
        user.uid if user else (f"guest:{session_id}" if session_id else None)
    )

    arq_pool = await get_arq_pool()
    redis_client = get_redis_client()

    if arq_pool is None or redis_client is None:
        # Redis 未接続時はフォールバックとして同期処理
        log.warning(
            "layout_lazy",
            "Redis unavailable, falling back to synchronous processing",
        )
        try:
            service = LayoutAnalysisService()
            all_figures = await service.analyze_layout_lazy(
                paper_id,
                parsed_pages,
                user_id=current_user_id,
                file_hash=file_hash,
                session_id=session_id,
            )
            return JSONResponse(
                {
                    "success": True,
                    "paper_id": paper_id,
                    "figures_detected": len(all_figures),
                    "figures": all_figures,
                }
            )
        except Exception as e:
            log.error("layout_lazy", "Synchronous fallback failed", error=str(e))
            raise HTTPException(status_code=500, detail="Layout analysis failed.")

    try:
        job_id = await enqueue_layout_job(
            arq_pool,
            redis_client,
            paper_id=paper_id,
            page_numbers=parsed_pages,
            user_id=current_user_id,
            file_hash=file_hash,
            session_id=session_id,
        )
        log.info("layout_lazy", "Job enqueued", job_id=job_id, paper_id=paper_id)
        return JSONResponse(
            {
                "success": True,
                "job_id": job_id,
                "status": "queued",
            }
        )
    except Exception as e:
        log.error("layout_lazy", "Failed to enqueue job", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to enqueue layout analysis job.")


@router.get("/layout-jobs/{job_id}")
async def get_layout_job_status(job_id: str):
    """
    レイアウト解析ジョブのステータスと結果を返す。

    status: "queued" | "processing" | "completed" | "failed"
    """
    redis_client = get_redis_client()
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    job = get_job_status(redis_client, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    status = job.get("status")

    if status == "completed":
        figures = job.get("result", [])
        return JSONResponse(
            {
                "success": True,
                "job_id": job_id,
                "status": "completed",
                "figures_detected": len(figures),
                "figures": figures,
            }
        )

    return JSONResponse(
        {
            "success": True,
            "job_id": job_id,
            "status": status,
            "error": job.get("error"),
        }
    )


@router.get("/layout-jobs/{job_id}/stream")
async def stream_layout_job(job_id: str):
    """
    レイアウト解析ジョブの完了をSSEでプッシュ通知する。

    クライアントはポーリングせず、この接続を維持するだけでよい。
    status: "queued" | "processing" | "completed" | "failed" | "timeout" | "not_found"
    """
    redis_client = get_redis_client()
    if redis_client is None:
        raise HTTPException(status_code=503, detail="Redis unavailable")

    async def generate():
        TIMEOUT = 125.0
        HEARTBEAT_INTERVAL = 15.0
        deadline = asyncio.get_event_loop().time() + TIMEOUT
        last_heartbeat = asyncio.get_event_loop().time()

        # 現在のステータスを即時チェック（ジョブが既に完了/失敗している場合に対応）
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

        # Pub/Sub で完了通知を待つ（失敗時はポーリングにフォールバック）
        pubsub = None
        use_pubsub = False
        from app.workers.layout_job import JOB_PUB_PREFIX
        try:
            pubsub = redis_client.pubsub()
            await asyncio.to_thread(pubsub.subscribe, f"{JOB_PUB_PREFIX}{job_id}")
            use_pubsub = True
        except Exception as e:
            log.warning("stream_layout", "Pub/Sub unavailable, falling back to polling", error=str(e))
            if pubsub:
                try:
                    await asyncio.to_thread(pubsub.unsubscribe)
                except Exception:
                    pass
                pubsub = None

        try:
            if use_pubsub:
                # Pub/Sub モード
                while asyncio.get_event_loop().time() < deadline:
                    now = asyncio.get_event_loop().time()
                    if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                        yield ": heartbeat\n\n"
                        last_heartbeat = now

                    try:
                        message = await asyncio.to_thread(
                            pubsub.get_message, ignore_subscribe_messages=True, timeout=1.0
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
                POLL_INTERVAL = 1.0
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
                    await asyncio.sleep(POLL_INTERVAL)

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
        },
    )
