"""
Analysis Router
Handles paper analysis features: summary, research radar, paragraph explanation,
figure/table analysis, and adversarial review.
"""

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from ..features import (
    AdversarialReviewService,
    CiteIntentService,
    ClaimVerificationService,
    FigureInsightService,
    ParagraphExplainService,
    ResearchRadarService,
    SummaryService,
)
from ..logger import logger
from ..providers import RedisService, get_storage_provider

router = APIRouter(tags=["Analysis"])

# Services
summary_service = SummaryService()
research_radar_service = ResearchRadarService()
paragraph_explain_service = ParagraphExplainService()
figure_insight_service = FigureInsightService()
adversarial_service = AdversarialReviewService()
cite_intent_service = CiteIntentService()
claim_service = ClaimVerificationService()
redis_service = RedisService()
storage = get_storage_provider()


def _get_context(session_id: str) -> str | None:
    """Get paper context from Redis or DB fallback."""
    # 1. Try Redis
    context = redis_service.get(f"session:{session_id}")
    if context:
        return context

    # 2. Try DB persistence (Session mapping)
    paper_id = storage.get_session_paper_id(session_id) or session_id

    # 3. Get Paper
    paper = storage.get_paper(paper_id)
    if paper and paper.get("ocr_text"):
        context = paper["ocr_text"]
        # Restore cache
        redis_service.set(f"session:{session_id}", context, expire=3600)
        logger.info(f"Restored context from DB for session {session_id} -> paper {paper_id}")
        return context

    return None


# ============================================================================
# Summary
# ============================================================================


@router.post("/summarize")
async def summarize(session_id: str = Form(...), mode: str = Form("full"), lang: str = Form("ja")):
    context = _get_context(session_id)
    if not context:
        logger.warning(f"[summarize] Context not found for session {session_id}")
        return JSONResponse(
            {"error": f"論文が読み込まれていません (session_id: {session_id})"}, status_code=400
        )
    logger.info(f"[summarize] session_id={session_id}, context_len={len(context)}")

    if mode == "sections":
        sections = await summary_service.summarize_sections(context, target_lang=lang)
        return JSONResponse({"sections": sections})
    elif mode == "abstract":
        abstract = await summary_service.summarize_abstract(context, target_lang=lang)
        return JSONResponse({"abstract": abstract})
    else:
        summary = await summary_service.summarize_full(context, target_lang=lang)
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
# Paragraph Explanation
# ============================================================================


@router.post("/explain-paragraph")
async def explain_paragraph(
    paragraph: str = Form(...), session_id: str = Form(...), lang: str = Form("ja")
):
    context = _get_context(session_id)
    explanation = await paragraph_explain_service.explain(paragraph, context or "", lang=lang)
    return JSONResponse({"explanation": explanation})


@router.post("/explain-terms")
async def explain_terms(paragraph: str = Form(...), lang: str = Form("ja")):
    terms = await paragraph_explain_service.explain_terminology(paragraph, lang=lang)
    return JSONResponse({"terms": terms})


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


@router.post("/identify-limitations")
async def identify_limitations(session_id: str = Form(...)):
    context = _get_context(session_id)
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    limitations = await adversarial_service.identify_limitations(context)
    return JSONResponse({"limitations": limitations})


@router.post("/counterarguments")
async def counterarguments(claim: str = Form(...), session_id: str = Form("")):
    context = _get_context(session_id) or ""
    args = await adversarial_service.suggest_counterarguments(claim, context)
    return JSONResponse({"counterarguments": args})


# ============================================================================
# Claim Verification
# ============================================================================


@router.post("/verify-claims")
async def verify_claims(paragraph: str = Form(...), lang: str = Form("ja")):
    report = await claim_service.verify_paragraph(paragraph, lang=lang)
    return JSONResponse({"report": report})


# ============================================================================
# Cite Intent
# ============================================================================


@router.post("/cite-intent")
async def analyze_cite_intent(paragraph: str = Form(...), lang: str = Form("ja")):
    intents = await cite_intent_service.analyze_paragraph_citations(paragraph, lang=lang)
    return JSONResponse({"citations": intents})
