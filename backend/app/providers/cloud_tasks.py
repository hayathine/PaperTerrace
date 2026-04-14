"""
Cloud Tasks プロバイダー
OCR 処理タスクを Cloud Tasks キューにエンキューする。
"""

from __future__ import annotations

import base64
import json

import httpx
from common import settings
from common.logger import ServiceLogger

log = ServiceLogger("CloudTasks")


def _get_access_token() -> str | None:
    """GCP サービスアカウント認証トークンを取得する。"""
    try:
        import google.auth
        import google.auth.transport.requests

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/cloud-platform"]
        )
        req = google.auth.transport.requests.Request()
        credentials.refresh(req)
        return credentials.token
    except Exception as e:
        log.warning("get_token", f"Failed to get GCP access token: {e}")
        return None


async def enqueue_ocr_task(task_id: str, payload: dict) -> bool:
    """OCR 処理タスクを Cloud Tasks キューにエンキューする。

    Args:
        task_id: Redis タスク ID。
        payload: ワーカーに渡すジョブデータ（file_hash, pdf_path 等）。

    Returns:
        エンキュー成功なら True。
    """
    queue_path = str(settings.get("CLOUD_TASKS_QUEUE_PATH", ""))
    worker_url = str(settings.get("WORKER_SERVICE_URL", ""))

    if not queue_path or not worker_url:
        log.warning(
            "enqueue",
            "CLOUD_TASKS_QUEUE_PATH または WORKER_SERVICE_URL が未設定です。インライン処理にフォールバックします。",
        )
        return False

    token = _get_access_token()
    if not token:
        log.error("enqueue", "GCP トークン取得失敗。Cloud Tasks エンキュー中断。")
        return False

    body_bytes = json.dumps({"task_id": task_id, **payload}).encode()
    task_body = {
        "task": {
            "httpRequest": {
                "httpMethod": "POST",
                "url": f"{worker_url}/api/internal/process-ocr",
                "headers": {"Content-Type": "application/json"},
                "body": base64.b64encode(body_bytes).decode(),
                "oidcToken": {
                    "serviceAccountEmail": str(
                        settings.get("WORKER_SA_EMAIL", "")
                    ),
                    "audience": worker_url,
                },
            }
        }
    }

    # OIDC SA が未設定の場合はフィールドを省略
    if not task_body["task"]["httpRequest"]["oidcToken"]["serviceAccountEmail"]:
        del task_body["task"]["httpRequest"]["oidcToken"]

    tasks_api_url = (
        f"https://cloudtasks.googleapis.com/v2/{queue_path}/tasks"
    )

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                tasks_api_url,
                json=task_body,
                headers={"Authorization": f"Bearer {token}"},
            )
            if resp.status_code == 200:
                task_name = resp.json().get("name", "")
                log.info(
                    "enqueue",
                    "Cloud Task をエンキューしました",
                    task_id=task_id,
                    cloud_task_name=task_name,
                )
                return True
            else:
                log.error(
                    "enqueue",
                    "Cloud Tasks API エラー",
                    status=resp.status_code,
                    body=resp.text[:200],
                )
                return False
    except Exception as e:
        log.error("enqueue", f"Cloud Tasks エンキュー例外: {e}", task_id=task_id)
        return False
