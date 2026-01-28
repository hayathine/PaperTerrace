"""
Analysis Router
Handles paper analysis features: summary, research radar, paragraph explanation,
figure/table analysis, and adversarial review.
"""

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from ..features import (
    AdversarialReviewService,
    ClaimVerificationService,
    FigureInsightService,
    ParagraphExplainService,
    ResearchRadarService,
    SummaryService,
)
from ..providers import RedisService

router = APIRouter(tags=["Analysis"])

# Services
summary_service = SummaryService()
research_radar_service = ResearchRadarService()
paragraph_explain_service = ParagraphExplainService()
figure_insight_service = FigureInsightService()
adversarial_service = AdversarialReviewService()
claim_service = ClaimVerificationService()
redis_service = RedisService()


# ============================================================================
# Summary
# ============================================================================


@router.post("/summarize")
async def summarize(session_id: str = Form(...), mode: str = Form("full"), lang: str = Form("ja")):
    context = redis_service.get(f"session:{session_id}") or ""
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

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
    context = redis_service.get(f"session:{session_id}") or ""
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    papers = await research_radar_service.find_related_papers(context[:3000])
    queries = await research_radar_service.generate_search_queries(context[:3000])
    return JSONResponse({"related_papers": papers, "search_queries": queries})


@router.post("/analyze-citations")
async def analyze_citations(session_id: str = Form(...)):
    context = redis_service.get(f"session:{session_id}") or ""
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
    context = redis_service.get(f"session:{session_id}") or ""
    explanation = await paragraph_explain_service.explain(paragraph, context, lang=lang)
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
    context = redis_service.get(f"session:{session_id}") or ""
    analysis = await figure_insight_service.analyze_table_text(table_text, context)
    return JSONResponse({"analysis": analysis})


# ============================================================================
# Adversarial Review
# ============================================================================


@router.post("/critique")
async def critique(session_id: str = Form(...), lang: str = Form("ja")):
    context = redis_service.get(f"session:{session_id}") or ""
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    critique = await adversarial_service.critique(context)
    return JSONResponse(critique)


@router.post("/identify-limitations")
async def identify_limitations(session_id: str = Form(...)):
    context = redis_service.get(f"session:{session_id}") or ""
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    limitations = await adversarial_service.identify_limitations(context)
    return JSONResponse({"limitations": limitations})


@router.post("/counterarguments")
async def counterarguments(claim: str = Form(...), session_id: str = Form("")):
    context = redis_service.get(f"session:{session_id}") or ""
    args = await adversarial_service.suggest_counterarguments(claim, context)
    return JSONResponse({"counterarguments": args})


# ============================================================================
# Claim Verification
# ============================================================================


@router.post("/verify-claims")
async def verify_claims(paragraph: str = Form(...), lang: str = Form("ja")):
    report = await claim_service.verify_paragraph(paragraph, lang=lang)
    return JSONResponse({"report": report})
