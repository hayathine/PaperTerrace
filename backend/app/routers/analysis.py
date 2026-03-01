"""
Analysis Router
Handles paper analysis features: summary,
figure/table analysis, layout detection, and adversarial review.
"""

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.domain.features import (
    AdversarialReviewService,
    FigureInsightService,
    SummaryService,
)
from app.domain.services.layout_analysis_service import LayoutAnalysisService
from app.providers import (
    RedisService,
    get_storage_provider,
)  # RedisService now uses in-memory cache
from common.logger import logger

router = APIRouter(tags=["Analysis"])

# Services
summary_service = SummaryService()
figure_insight_service = FigureInsightService()
adversarial_service = AdversarialReviewService()
redis_service = RedisService()
storage = get_storage_provider()
layout_analysis_service = LayoutAnalysisService()


def _get_context(session_id: str) -> str | None:
    """Get paper context from cache or DB fallback."""
    # 1. Try DB first for analysis reliability and to prevent Redis OOM with large blobs.
    # Higher reliability by always ensuring we have the full document.
    paper_id = storage.get_session_paper_id(session_id)
    resolved_paper_id = paper_id or session_id

    # Try DB persistence
    paper = storage.get_paper(resolved_paper_id)
    if paper and paper.get("ocr_text"):
        context = paper["ocr_text"]
        logger.debug(
            f"[_get_context] Fetched FULL context from DB for {resolved_paper_id}"
        )
        return context

    # 2. Fallback to session cache (recent context)
    context = redis_service.get(f"session:{session_id}")
    if context:
        logger.debug(f"[_get_context] Cache HIT for session {session_id}")
        redis_service.expire(f"session:{session_id}", 3600)
        return context
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
):
    context = _get_context(session_id)
    if not context:
        logger.warning(f"[summarize] Context not found for session {session_id}")
        return JSONResponse(
            {"error": f"論文が読み込まれていません (session_id: {session_id})"},
            status_code=400,
        )

    # Resolve paper_id if missing
    if not paper_id:
        paper_id = storage.get_session_paper_id(session_id)

    # Clear cached summary if force=True
    if force and paper_id:
        logger.info(f"[summarize] Force regeneration requested for {paper_id}")
        storage.update_paper_full_summary(paper_id, "")

    logger.info(
        f"[summarize] session_id={session_id}, paper_id={paper_id}, context_len={len(context)}, force={force}"
    )

    summary = await summary_service.summarize_full(
        context, target_lang=lang, paper_id=paper_id, key_word=key_word
    )
    return JSONResponse({"summary": summary})


# ============================================================================
# Figure Insight
# ============================================================================


@router.post("/analyze-figure")
async def analyze_figure(file: UploadFile = File(...), caption: str = Form("")):
    content = await file.read()
    mime_type = file.content_type or "image/png"
    analysis = await figure_insight_service.analyze_figure(content, caption, mime_type)
    return JSONResponse({"analysis": analysis})


# ============================================================================
# Adversarial Review
# ============================================================================


@router.post("/critique")
async def critique(session_id: str = Form(...), lang: str = Form("ja")):
    context = _get_context(session_id)
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    critique = await adversarial_service.critique(context)
    return JSONResponse(critique)


# ============================================================================
# Layout Detection
# ============================================================================


@router.post("/analyze-layout-lazy")
async def analyze_layout_lazy(
    paper_id: str = Form(...),
    page_numbers: str | None = Form(None),
):
    """
    画面表示後に遅延実行されるレイアウト解析エンドポイント（バッチ処理版）
    """
    try:
        # Parse page numbers
        parsed_pages = None
        if page_numbers:
            try:
                parsed_pages = [int(p.strip()) for p in page_numbers.split(",")]
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Invalid page_numbers format"
                )

        all_figures = await layout_analysis_service.analyze_layout_lazy(
            paper_id, parsed_pages
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
        logger.error(f"[analyze-layout-lazy] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Layout analysis failed: {str(e)}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[analyze-layout-lazy] Unexpected error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Layout analysis failed: {str(e)}")
