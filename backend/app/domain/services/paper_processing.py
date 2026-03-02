import os

import httpx

from app.domain.features.figure_insight import FigureInsightService
from app.domain.features.summary import SummaryService
from app.providers import get_storage_provider
from common.logger import ServiceLogger

log = ServiceLogger("Processing")
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

    log.info("figure_task", "Analysis task started", figure_id=figure_id)

    try:
        figure = storage.get_figure(figure_id)
        if not figure:
            log.warning("figure_task", "Figure not found in DB", figure_id=figure_id)
            return

        # Skip if already has explanation
        if figure.get("explanation"):
            log.info(
                "figure_task",
                "Figure already has explanation, skipping.",
                figure_id=figure_id,
            )
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
            log.warning(
                "figure_task", "Could not retrieve image bytes", image_url=image_url
            )
            return

        # All visual elements (figures, tables, equations) are handled via general AI analysis
        explanation = await figure_insight.analyze_figure(
            image_bytes,
            caption=figure.get("caption", ""),
            target_lang=lang,
        )
        storage.update_figure_explanation(figure_id, explanation)

        label = figure.get("label", "figure")
        log.info(
            "figure_task", "SUCCESS: updated analysis", label=label, figure_id=figure_id
        )

    except Exception as e:
        log.error(
            "figure_task",
            "Analysis FAILED",
            figure_id=figure_id,
            error=str(e),
            exc_info=True,
        )


async def process_paper_summary_task(paper_id: str, lang: str = "ja"):
    """
    Background task to summarize paper.
    """
    if not paper_id:
        return

    log.info("summary_task", "Summary task started", paper_id=paper_id)

    try:
        paper = storage.get_paper(paper_id)
        if not paper or not paper.get("ocr_text"):
            log.warning(
                "summary_task", "Paper or its text not found", paper_id=paper_id
            )
            return

        # Skip if already has summary
        if paper.get("full_summary"):
            log.info(
                "summary_task",
                "Paper already has full summary, skipping.",
                paper_id=paper_id,
            )
            return

        # Execute summary
        await summary_service.summarize_full(
            text=paper["ocr_text"], target_lang=lang, paper_id=paper_id
        )
        log.info(
            "summary_task", "SUCCESS: generated summary for paper", paper_id=paper_id
        )

    except Exception as e:
        log.error(
            "summary_task",
            "Summary FAILED",
            paper_id=paper_id,
            error=str(e),
            exc_info=True,
        )
