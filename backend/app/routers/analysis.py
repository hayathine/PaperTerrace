"""
Analysis Router
Handles paper analysis features: summary, research radar,
figure/table analysis, layout detection, and adversarial review.
"""

import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.domain.features import (
    AdversarialReviewService,
    CiteIntentService,
    ClaimVerificationService,
    FigureInsightService,
    ResearchRadarService,
    SummaryService,
)
from app.domain.services.layout_service import get_layout_service
from app.providers import (
    RedisService,
    get_storage_provider,
)  # RedisService now uses in-memory cache
from common.logger import logger

router = APIRouter(tags=["Analysis"])

# Services
summary_service = SummaryService()
research_radar_service = ResearchRadarService()
figure_insight_service = FigureInsightService()
adversarial_service = AdversarialReviewService()
cite_intent_service = CiteIntentService()
claim_service = ClaimVerificationService()
redis_service = RedisService()
storage = get_storage_provider()
layout_service = get_layout_service()


def _get_context(session_id: str) -> str | None:
    """Get paper context from cache or DB fallback."""
    # 1. Try in-memory cache
    context = redis_service.get(f"session:{session_id}")
    if context:
        logger.debug(
            f"[_get_context] Cache HIT for session {session_id} (len={len(context)})"
        )
        return context

    logger.info(
        f"[_get_context] Cache MISS for session {session_id}. debug: exists={redis_service.exists(f'session:{session_id}')}"
    )

    # 2. Try DB persistence (Session mapping)
    paper_id = storage.get_session_paper_id(session_id)
    resolved_paper_id = paper_id or session_id

    logger.info(
        f"[_get_context] DB Session Lookup: session_id={session_id} -> paper_id={paper_id}. resolved={resolved_paper_id}"
    )

    # 3. Get Paper
    paper = storage.get_paper(resolved_paper_id)
    if paper:
        if paper.get("ocr_text"):
            context = paper["ocr_text"]
            # Restore cache
            redis_service.set(f"session:{session_id}", context, expire=3600)
            logger.info(
                f"[_get_context] Restored context from DB for session {session_id} -> paper {resolved_paper_id} (len={len(context)})"
            )
            return context
        else:
            logger.warning(
                f"[_get_context] Paper found in DB ({resolved_paper_id}) but 'ocr_text' is Empty/None."
            )
    else:
        logger.warning(f"[_get_context] Paper NOT found in DB. ID: {resolved_paper_id}")

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

    logger.info(
        f"[summarize] session_id={session_id}, paper_id={paper_id}, context_len={len(context)}"
    )

    summary = await summary_service.summarize_full(
        context, target_lang=lang, paper_id=paper_id
    )
    return JSONResponse({"summary": summary})


# ============================================================================
# Research Radar
# ============================================================================


@router.post("/research-radar")
async def research_radar(session_id: str = Form(...), lang: str = Form("ja")):
    context = _get_context(session_id)
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    papers = await research_radar_service.find_related_papers(context[:3000])
    queries = await research_radar_service.generate_search_queries(context[:3000])
    return JSONResponse({"related_papers": papers, "search_queries": queries})


@router.post("/analyze-citations")
async def analyze_citations(session_id: str = Form(...)):
    context = _get_context(session_id)
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    citations = await research_radar_service.analyze_citations(context)
    return JSONResponse({"citations": citations})


# ============================================================================
# Figure Insight
# ============================================================================


@router.post("/analyze-figure")
async def analyze_figure(file: UploadFile = File(...), caption: str = Form("")):
    content = await file.read()
    mime_type = file.content_type or "image/png"
    analysis = await figure_insight_service.analyze_figure(content, caption, mime_type)
    return JSONResponse({"analysis": analysis})


@router.post("/analyze-table")
async def analyze_table(table_text: str = Form(...), session_id: str = Form("")):
    context = _get_context(session_id) or ""
    analysis = await figure_insight_service.analyze_table_text(table_text, context)
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
# Claim Verification
# ============================================================================


@router.post("/verify-claims")
async def verify_claims(paragraph: str = Form(...), lang: str = Form("ja")):
    report = await claim_service.verify_paragraph(paragraph, lang=lang)
    return JSONResponse({"report": report})


# ============================================================================
# Layout Detection
# ============================================================================


@router.post("/detect-layout")
async def detect_layout(
    file: UploadFile = File(..., description="PDF page image file"),
    page_number: int = Form(1, description="Page number for reference"),
):
    """
    画像からレイアウト要素（図、表、数式など）を検出

    Parameters
    ----------
    file : UploadFile
        解析対象のPDF画像ファイル（PNG, JPEG対応）
    page_number : int
        ページ番号（参照用）

    Returns
    -------
    JSONResponse
        検出されたレイアウト要素のリスト
    """
    # ファイル形式チェック
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type: {file.content_type}. Only image files are supported.",
        )

    try:
        logger.info(
            f"Layout detection request: file={file.filename}, page={page_number}, type={file.content_type}"
        )

        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            # レイアウト解析実行
            layout_items = await layout_service.analyze_image(temp_file_path)

            # レスポンス形式に変換
            results = []
            for item in layout_items:
                results.append(
                    {
                        "class_name": item.class_name,
                        "confidence": item.score,
                        "bbox": {
                            "x_min": item.bbox.x_min,
                            "y_min": item.bbox.y_min,
                            "x_max": item.bbox.x_max,
                            "y_max": item.bbox.y_max,
                        },
                    }
                )

            logger.info(f"Layout detection completed: {len(results)} elements detected")

            return JSONResponse(
                {
                    "success": True,
                    "page_number": page_number,
                    "total_elements": len(results),
                    "elements": results,
                }
            )

        finally:
            # 一時ファイルを削除
            Path(temp_file_path).unlink(missing_ok=True)

    except Exception as e:
        logger.error(f"Layout detection failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Layout detection failed: {str(e)}"
        )


# ============================================================================
# Cite Intent
# ============================================================================


@router.post("/cite-intent")
async def analyze_cite_intent(paragraph: str = Form(...), lang: str = Form("ja")):
    intents = await cite_intent_service.analyze_paragraph_citations(
        paragraph, lang=lang
    )
    return JSONResponse({"citations": intents})
