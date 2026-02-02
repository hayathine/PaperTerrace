import json
import os
from typing import Any, Dict, Optional

from google.cloud import tasks_v2

from src.core.logger import logger


class CloudTasksService:
    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID")
        self.location = os.getenv("GOOGLE_CLOUD_LOCATION", "asia-northeast1")
        self.queue_name = os.getenv("CLOUD_TASKS_QUEUE", "paper-analysis-queue")
        self.base_url = os.getenv("APP_BASE_URL")  # e.g., https://your-app.com
        self.client = None

        if self.project_id:
            try:
                self.client = tasks_v2.CloudTasksClient()
            except Exception as e:
                logger.warning(f"Failed to initialize Cloud Tasks client: {e}")

    def _get_parent(self) -> str:
        return f"projects/{self.project_id}/locations/{self.location}/queues/{self.queue_name}"

    def enqueue(self, task_type: str, payload: Dict[str, Any]) -> bool:
        """
        Enqueue a task to Cloud Tasks.
        If GCP_PROJECT_ID is not set or client fails, returns False to indicate fallback needed.
        """
        if not self.client or not self.project_id or not self.base_url:
            logger.debug(f"Cloud Tasks not configured, fallback needed for task {task_type}")
            return False

        parent = self._get_parent()
        url = f"{self.base_url}/api/v1/tasks/handler"

        task_payload = {"type": task_type, "data": payload}

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-type": "application/json"},
                "body": json.dumps(task_payload).encode(),
            }
        }

        # Add OIDC token for authentication in production
        service_account_email = os.getenv("GCP_SERVICE_ACCOUNT")
        if service_account_email:
            task["http_request"]["oidc_token"] = {"service_account_email": service_account_email}

        try:
            response = self.client.create_task(request={"parent": parent, "task": task})
            logger.info(f"Task created: {response.name} (type: {task_type})")
            return True
        except Exception as e:
            logger.error(f"Failed to create Cloud Task: {e}")
            return False

    def enqueue_figure_analysis(
        self,
        figure_id: str,
        image_url: str,
        label: str = "figure",
        target_lang: str = "ja",
        content: Optional[str] = None,
    ):
        payload = {
            "figure_id": figure_id,
            "image_url": image_url,
            "label": label,
            "target_lang": target_lang,
            "content": content,
        }
        if not self.enqueue("figure_analysis", payload):
            # Fallback to local background task
            import asyncio

            from src.api.v1.endpoints.pdf import process_figure_auto_analysis

            logger.debug(f"Falling back to local execution for figure {figure_id}")
            asyncio.create_task(
                process_figure_auto_analysis(
                    figure_id=figure_id,
                    image_url=image_url,
                    label=label,
                    target_lang=target_lang,
                    content=content,
                )
            )

    def enqueue_paper_summary(
        self,
        paper_id: str,
        full_text: str,
        target_lang: str = "ja",
        file_hash: Optional[str] = None,
    ):
        payload = {
            "paper_id": paper_id,
            "full_text": full_text,
            "target_lang": target_lang,
            "file_hash": file_hash,
        }
        if not self.enqueue("paper_summary", payload):
            # Fallback
            import asyncio

            from src.domain.features.summary import SummaryService
            from src.infra import get_image_bytes, get_page_images, get_storage_provider

            async def run_summary():
                storage = get_storage_provider()
                summary_service = SummaryService()
                try:
                    # Try integrated analysis if images are available
                    image_data_list = []
                    if file_hash:
                        image_urls = get_page_images(file_hash)
                        if image_urls:
                            # Use first 20 pages for integrated analysis
                            for i, _ in enumerate(image_urls[:20]):
                                img_bytes = get_image_bytes(file_hash, i + 1)
                                if img_bytes:
                                    image_data_list.append((img_bytes, "image/png"))

                    if image_data_list:
                        logger.info(
                            f"Running integrated analysis for paper {paper_id} with {len(image_data_list)} images"
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

                        # Save visual elements to DB
                        try:
                            for item in integrated.all_detected_items:
                                storage.save_figure(
                                    paper_id=paper_id,
                                    page_number=item.page_num,
                                    bbox=item.box_2d,
                                    image_url="",
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
                        summary = await summary_service.summarize_full(
                            full_text, target_lang=target_lang
                        )

                    if summary:
                        storage.update_paper_abstract(paper_id, summary)
                        logger.info(f"Local auto-summary generated for paper {paper_id}")
                except Exception as e:
                    logger.error(f"Local auto-summary failed for paper {paper_id}: {e}")

            asyncio.create_task(run_summary())


cloud_tasks_service = CloudTasksService()
