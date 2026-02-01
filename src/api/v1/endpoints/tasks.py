from fastapi import APIRouter, HTTPException, Request

from src.api.v1.endpoints.pdf import process_figure_auto_analysis
from src.core.logger import logger
from src.domain.features.summary import SummaryService
from src.infra import get_storage_provider

router = APIRouter(tags=["Internal Tasks"])


@router.post("/tasks/handler")
async def tasks_handler(request: Request):
    """
    Internal handler for Cloud Tasks callbacks.
    """
    payload = await request.json()
    task_type = payload.get("type")
    data = payload.get("data", {})

    logger.info(f"Received task: {task_type}")

    if task_type == "figure_analysis":
        await process_figure_auto_analysis(
            figure_id=data["figure_id"],
            image_url=data["image_url"],
            label=data.get("label", "figure"),
            target_lang=data.get("target_lang", "ja"),
            content=data.get("content"),
        )

    elif task_type == "paper_summary":
        paper_id = data["paper_id"]
        full_text = data["full_text"]
        target_lang = data.get("target_lang", "ja")

        storage = get_storage_provider()
        summary_service = SummaryService()

        try:
            summary = await summary_service.summarize_full(full_text, target_lang=target_lang)
            if summary:
                storage.update_paper_abstract(paper_id, summary)
                logger.info(f"Auto-summary completed for paper {paper_id} via Cloud Tasks")
        except Exception as e:
            logger.error(f"Auto-summary failed for paper {paper_id}: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    else:
        logger.warning(f"Unknown task type: {task_type}")
        raise HTTPException(status_code=400, detail="Unknown task type")

    return {"status": "ok"}
