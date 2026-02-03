import os

from fastapi import APIRouter, HTTPException, Request

from src.domain.features.figure_insight import FigureInsightService
from src.domain.features.summary import SummaryService
from src.logger import logger
from src.providers import get_storage_provider

router = APIRouter(prefix="/tasks", tags=["Tasks"])
storage = get_storage_provider()
figure_insight = FigureInsightService()
summary_service = SummaryService(storage=storage)


@router.post("/handler")
async def tasks_handler(request: Request):
    """
    Unified handler for Cloud Tasks.
    Validation of OIDC token should be done here in production.
    """
    # For now, we trust the internal network or check a simple secret if provided
    # TODO: Verify X-AppEngine-QueueName or OIDC

    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    task_type = payload.get("type")
    logger.info(f"Received Cloud Task: {task_type}")

    if task_type == "figure_analysis":
        await handle_figure_analysis(payload)
    elif task_type == "paper_summary":
        await handle_paper_summary(payload)
    else:
        logger.warning(f"Unknown task type: {task_type}")
        raise HTTPException(status_code=400, detail=f"Unknown task type: {task_type}")

    return {"status": "ok"}


async def handle_figure_analysis(payload: dict):
    figure_id = payload.get("figure_id")
    image_url = payload.get("image_url")
    if not figure_id:
        return

    logger.info(f"Processing figure analysis for {figure_id}")
    figure = storage.get_figure(figure_id)
    if not figure:
        logger.warning(f"Figure {figure_id} not found in DB")
        return

    # Skip if already has explanation
    if figure.get("explanation"):
        logger.info(f"Figure {figure_id} already has explanation, skipping.")
        return

    # Logic to get image bytes (adapted from figures.py)
    image_bytes = None
    if image_url.startswith("/static/"):
        file_path = f"src/{image_url.lstrip('/')}"
        if os.path.exists(file_path):
            with open(file_path, "rb") as f:
                image_bytes = f.read()
    elif image_url.startswith("http"):
        import httpx

        async with httpx.AsyncClient() as client:
            resp = await client.get(image_url)
            if resp.status_code == 200:
                image_bytes = resp.content

    if not image_bytes:
        logger.warning(f"Could not retrieve image bytes for {image_url}")
        return

    try:
        label = figure.get("label", "figure")
        if label == "equation":
            from src.domain.features.figure_insight.equation_service import EquationService

            eq_service = EquationService()
            analysis = await eq_service._analyze_bbox_with_ai(
                image_bytes, target_lang=payload.get("lang", "ja")
            )
            if analysis:
                storage.update_figure_explanation(figure_id, analysis.explanation)
                storage.update_figure_latex(figure_id, analysis.latex)
        else:
            explanation = await figure_insight.analyze_figure(
                image_bytes,
                caption=figure.get("caption", ""),
                target_lang=payload.get("lang", "ja"),
            )
            storage.update_figure_explanation(figure_id, explanation)

        logger.info(f"Successfully updated analysis for {label} {figure_id}")
    except Exception as e:
        logger.error(f"Figure analysis failed for {figure_id}: {e}")
        raise  # Re-raise to trigger Cloud Tasks retry


async def handle_paper_summary(payload: dict):
    paper_id = payload.get("paper_id")
    lang = payload.get("lang", "ja")
    if not paper_id:
        return

    logger.info(f"Processing paper summary for {paper_id}")
    paper = storage.get_paper(paper_id)
    if not paper or not paper.get("ocr_text"):
        logger.warning(f"Paper {paper_id} or its text not found")
        return

    # Skip if already has summary
    if paper.get("full_summary"):
        logger.info(f"Paper {paper_id} already has full summary, skipping.")
        return

    try:
        await summary_service.summarize_full(
            text=paper["ocr_text"], target_lang=lang, paper_id=paper_id
        )
        # Note: summarize_full with paper_id already updates the storage
        logger.info(f"Successfully generated summary for paper {paper_id}")
    except Exception as e:
        logger.error(f"Paper summary failed for {paper_id}: {e}")
        raise  # Re-raise to trigger Cloud Tasks retry
