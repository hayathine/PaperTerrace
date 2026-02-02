"""
Analysis Router
Handles paper analysis features: summary, research radar, paragraph explanation,
figure/table analysis, and adversarial review.
"""

from fastapi import APIRouter, File, Form, UploadFile
from fastapi.responses import JSONResponse

from src.core.logger import logger
from src.domain.features import (
    AdversarialReviewService,
    CiteIntentService,
    ClaimVerificationService,
    FigureInsightService,
    ResearchRadarService,
    SummaryService,
)
from src.infra import (
    RedisService,
    get_image_bytes,
    get_page_images,
    get_storage_provider,
)

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


def _get_context(session_id: str) -> str | None:
    """Get paper context from Redis or DB fallback."""
    # 1. Try Redis
    context = redis_service.get(f"session:{session_id}")
    if context:
        logger.debug(f"[_get_context] Redis HIT for session {session_id} (len={len(context)})")
        return context

    logger.info(
        f"[_get_context] Redis MISS for session {session_id}. debug: exists={redis_service.exists(f'session:{session_id}')}"
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
async def summarize(session_id: str = Form(...), mode: str = Form("full"), lang: str = Form("ja")):
    context = _get_context(session_id)
    if not context:
        logger.warning(f"[summarize] Context not found for session {session_id}")
        return JSONResponse(
            {"error": f"論文が読み込まれていません (session_id: {session_id})"}, status_code=400
        )
    logger.info(f"[summarize] session_id={session_id}, context_len={len(context)}")

    try:
        if mode == "sections":
            sections = await summary_service.summarize_sections(context, target_lang=lang)
            return JSONResponse({"sections": sections})
        elif mode == "abstract":
            # Check DB first
            paper_id = storage.get_session_paper_id(session_id)
            if paper_id:
                paper = storage.get_paper(paper_id)
                if paper and paper.get("abstract"):
                    logger.info(f"[summarize] Cache HIT for abstract: {paper_id}")
                    return JSONResponse({"abstract": paper["abstract"]})

            abstract = await summary_service.summarize_abstract(context, target_lang=lang)

            # Save generated abstract if paper exists
            if paper_id:
                storage.update_paper_abstract(paper_id, abstract)

            return JSONResponse({"abstract": abstract})
        else:
            # Integrated analysis for full summary
            paper_id = storage.get_session_paper_id(session_id)
            file_hash = None
            if paper_id:
                paper = storage.get_paper(paper_id)
                if paper:
                    file_hash = paper.get("file_hash")

            if file_hash:
                image_urls = get_page_images(file_hash)
                if image_urls:
                    image_data_list = []
                    # Limit to first 20 pages for performance/cost if very long?
                    # Gemini 2.0 Flash should handle more, but let's be safe.
                    for i, url in enumerate(image_urls[:20]):
                        # URL is /static/paper_images/{file_hash}/page_{n}.png
                        # Extract page number or just iterate
                        page_num = i + 1
                        img_bytes = get_image_bytes(file_hash, page_num)
                        if img_bytes:
                            image_data_list.append((img_bytes, "image/png"))

                    if image_data_list:
                        integrated = await summary_service.analyze_integrated(
                            context, image_data_list, target_lang=lang
                        )
                        # Save detected items to DB for later use
                        if paper_id:
                            # TODO: Update paper/figures table with all_detected_items
                            # For now, we just return it
                            pass

                        return JSONResponse(integrated.model_dump())

            # Fallback to text-only if no images
            summary = await summary_service.summarize_full(context, target_lang=lang)
            return JSONResponse({"summary": summary})
    except Exception as e:
        logger.exception(f"[summarize] Failed to generate summary for session {session_id}")
        return JSONResponse({"error": f"要約の生成に失敗しました: {str(e)}"}, status_code=500)


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

    critique = await adversarial_service.critique(context, target_lang=lang)
    return JSONResponse(critique)


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
