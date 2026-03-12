"""
Analysis Router
Handles paper analysis features: summary,
figure/table analysis, layout detection, and adversarial review.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.auth import OptionalUser
from app.domain.features import (
    AdversarialReviewService,
    FigureInsightService,
    SummaryService,
)
from app.domain.services.layout_analysis_service import LayoutAnalysisService
from app.providers import (
    RedisService,
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
layout_analysis_service = LayoutAnalysisService()


def _get_context(session_id: str) -> str | None:
    """Get paper context from cache or DB fallback."""
    # 1. Redis キャッシュを優先して確認（DB クエリを省略）
    context = redis_service.get(f"session:{session_id}")
    if context:
        log.debug("get_context", "Cache HIT", session_id=session_id)
        redis_service.expire(f"session:{session_id}", 3600)
        return context

    # 2. DB から取得（キャッシュミス時のフォールバック）
    storage = get_storage_provider()
    paper_id = storage.get_session_paper_id(session_id)
    resolved_paper_id = paper_id or session_id

    paper = storage.get_paper(resolved_paper_id)
    if paper and paper.get("ocr_text"):
        log.debug(
            "get_context",
            "Fetched FULL context from DB",
            paper_id=resolved_paper_id,
        )
        return paper["ocr_text"]

    return None


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
    context = _get_context(session_id)
    if not context:
        log.warning("summarize", "Context not found", session_id=session_id)

        return JSONResponse(
            {"error": f"論文が読み込まれていません (session_id: {session_id})"},
            status_code=400,
        )

    storage = get_storage_provider()
    # Resolve paper_id if missing
    if not paper_id:
        paper_id = storage.get_session_paper_id(session_id)

    # Clear cached summary if force=True
    if force and paper_id:
        log.info("summarize", "Force regeneration requested", paper_id=paper_id)

        storage.update_paper_full_summary(paper_id, "")

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
    mime_type = file.content_type or "image/png"
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
    context = _get_context(session_id)
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

    redis_client = get_redis_client()
    if redis_client is None:
        # Redis 未接続時はフォールバックとして同期処理
        log.warning(
            "layout_lazy",
            "Redis unavailable, falling back to synchronous processing",
        )
        try:
            all_figures = await layout_analysis_service.analyze_layout_lazy(
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
        job_id = enqueue_layout_job(
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
