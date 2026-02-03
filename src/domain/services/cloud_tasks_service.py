import json
import os
from typing import Any, Dict

from google.cloud import tasks_v2

from src.logger import logger


class CloudTasksService:
    """
    Service for enqueuing heavy tasks to Google Cloud Tasks.
    Supports fallback to local execution if not configured.
    """

    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT")
        self.location_id = os.getenv("GCP_LOCATION", "us-central1")
        self.queue_id = os.getenv("GCP_QUEUE_ID", "paper-analysis-queue")
        self.worker_url = os.getenv("WORKER_URL")  # Root URL of the application
        self.service_account_email = os.getenv("SERVICE_ACCOUNT_EMAIL")

        # Determine if we should use Cloud Tasks or fallback
        # USE_CLOUD_TASKS must be explicitly "true"
        self.is_enabled = all(
            [self.project_id, self.worker_url, os.getenv("USE_CLOUD_TASKS") == "true"]
        )

        if self.is_enabled:
            try:
                self.client = tasks_v2.CloudTasksClient()
                self.parent = self.client.queue_path(
                    self.project_id, self.location_id, self.queue_id
                )
                logger.info(f"CloudTasksService initialized for queue: {self.parent}")
            except Exception as e:
                logger.error(f"Failed to initialize Cloud Tasks client: {e}")
                self.is_enabled = False
        else:
            logger.info("CloudTasksService initialized in fallback (Local/BackgroundTasks) mode")

    def enqueue_figure_analysis(self, figure_id: str, image_url: str):
        """Enqueue figure analysis task."""
        payload = {"type": "figure_analysis", "figure_id": figure_id, "image_url": image_url}
        return self._enqueue(payload)

    def enqueue_paper_summary(self, paper_id: str, lang: str = "ja"):
        """Enqueue paper summary task."""
        payload = {"type": "paper_summary", "paper_id": paper_id, "lang": lang}
        return self._enqueue(payload)

    def _enqueue(self, payload: Dict[str, Any]) -> bool:
        """Internal method to create a task in Cloud Tasks."""
        if not self.is_enabled:
            logger.info(f"Cloud Tasks Disabled: Task {payload['type']} would be processed locally.")
            return False

        # Cloud Tasks implementation
        url = f"{self.worker_url.rstrip('/')}/tasks/handler"

        task = {
            "http_request": {
                "http_method": tasks_v2.HttpMethod.POST,
                "url": url,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(payload).encode("utf-8"),
            }
        }

        if self.service_account_email:
            task["http_request"]["oidc_token"] = {
                "service_account_email": self.service_account_email,
            }

        try:
            response = self.client.create_task(request={"parent": self.parent, "task": task})
            logger.info(f"Cloud Task created: {response.name} for type {payload['type']}")
            return True
        except Exception as e:
            logger.error(f"Failed to create Cloud Task: {e}")
            return False


# Singleton instance
_instance = None


def get_cloud_tasks_service() -> CloudTasksService:
    global _instance
    if _instance is None:
        _instance = CloudTasksService()
    return _instance
