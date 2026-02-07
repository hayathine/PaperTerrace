import logging
import os

import httpx
from app.domain.features.figure_insight import FigureInsightService
from app.domain.features.summary import SummaryService
from app.providers import get_storage_provider

logger = logging.getLogger(__name__)
storage = get_storage_provider()
figure_insight = FigureInsightService()
summary_service = SummaryService(storage=storage)


async def process_figure_analysis_task(
    figure_id: str, image_url: str, lang: str = "ja"
):
    """
    Background task to analyze figure.
    """
    if not figure_id:
        return

    logger.info(f"[Task] Processing figure analysis for {figure_id}")
    try:
        figure = storage.get_figure(figure_id)
        if not figure:
            logger.warning(f"Figure {figure_id} not found in DB")
            return

        # Skip if already has explanation
        if figure.get("explanation"):
            logger.info(f"Figure {figure_id} already has explanation, skipping.")
            return

        # Retrieve image bytes
        image_bytes = None
        if image_url.startswith("/static/"):
            file_path = f"src/{image_url.lstrip('/')}"
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    image_bytes = f.read()
        elif image_url.startswith("http"):
            async with httpx.AsyncClient() as client:
                resp = await client.get(image_url, timeout=30.0)
                if resp.status_code == 200:
                    image_bytes = resp.content

        if not image_bytes:
            logger.warning(f"Could not retrieve image bytes for {image_url}")
            return

        # All visual elements (figures, tables, equations) are handled via general AI analysis
        explanation = await figure_insight.analyze_figure(
            image_bytes,
            caption=figure.get("caption", ""),
            target_lang=lang,
        )
        storage.update_figure_explanation(figure_id, explanation)

        label = figure.get("label", "figure")
        logger.info(f"[Task] Successfully updated analysis for {label} {figure_id}")

    except Exception as e:
        logger.error(f"[Task] Figure analysis failed for {figure_id}: {e}")


async def process_paper_summary_task(paper_id: str, lang: str = "ja"):
    """
    Background task to summarize paper.
    """
    if not paper_id:
        return

    logger.info(f"[Task] Processing paper summary for {paper_id}")
    try:
        paper = storage.get_paper(paper_id)
        if not paper or not paper.get("ocr_text"):
            logger.warning(f"Paper {paper_id} or its text not found")
            return

        # Skip if already has summary
        if paper.get("full_summary"):
            logger.info(f"Paper {paper_id} already has full summary, skipping.")
            return

        # Execute summary
        await summary_service.summarize_full(
            text=paper["ocr_text"], target_lang=lang, paper_id=paper_id
        )
        logger.info(f"[Task] Successfully generated summary for paper {paper_id}")

    except Exception as e:
        logger.error(f"[Task] Paper summary failed for {paper_id}: {e}")
