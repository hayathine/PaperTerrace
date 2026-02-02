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
        file_hash = data.get("file_hash")

        storage = get_storage_provider()
        summary_service = SummaryService()

        try:
            from src.infra import get_image_bytes, get_page_images

            # Try integrated analysis if images are available
            image_data_list = []
            if file_hash:
                image_urls = get_page_images(file_hash)
                if image_urls:
                    for i, _ in enumerate(image_urls[:20]):
                        img_bytes = get_image_bytes(file_hash, i + 1)
                        if img_bytes:
                            image_data_list.append((img_bytes, "image/png"))

            if image_data_list:
                logger.info(
                    f"Running integrated analysis for paper {paper_id} via Cloud Tasks with {len(image_data_list)} images"
                )
                integrated = await summary_service.analyze_integrated(
                    full_text, image_data_list, target_lang=target_lang
                )
                # Format integrated result as summary text for now
                summary = (
                    f"## Overview\n{integrated.overview}\n\n"
                    f"## Key Contributions\n"
                    + "\n".join([f"- {c.content}" for c in integrated.key_contributions])
                    + f"\n\n## Methodology\n{integrated.methodology.content}\n\n"
                    f"## Conclusion\n{integrated.conclusion.content}"
                )
                # Save detected items to DB if paper exists
                try:
                    for item in integrated.all_detected_items:
                        storage.save_figure(
                            paper_id=paper_id,
                            page_number=item.page_num,
                            bbox=item.box_2d,
                            image_url="",  # We don't have a cropped URL yet, but we have the grounding
                            caption=item.description or "",
                            label=item.type,
                            explanation=item.description or "",
                        )
                    logger.info(
                        f"Saved {len(integrated.all_detected_items)} grounded items for paper {paper_id}"
                    )
                except Exception as save_err:
                    logger.warning(f"Failed to save grounded items: {save_err}")
            else:
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
