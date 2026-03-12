"""
レイアウト解析ジョブのキュー管理ヘルパー

Redis の layout_job_queue にジョブを積み、ステータス・結果を管理する。
"""

import json
import uuid
from datetime import datetime, timezone
from typing import Any

JOB_QUEUE_KEY = "layout_job_queue"
JOB_KEY_PREFIX = "layout_job:"
JOB_TTL = 3600  # 1時間


def enqueue_layout_job(
    redis_client,
    paper_id: str,
    page_numbers: list[int] | None,
    user_id: str | None,
    file_hash: str | None,
    session_id: str | None,
) -> str:
    """レイアウト解析ジョブをキューに追加し job_id を返す"""
    job_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc).isoformat()

    job_payload = {
        "job_id": job_id,
        "paper_id": paper_id,
        "page_numbers": page_numbers,
        "user_id": user_id,
        "file_hash": file_hash,
        "session_id": session_id,
        "created_at": now,
    }

    # ステータスキーを先に登録しておく（pending 状態）
    status_data = {"status": "queued", "created_at": now}
    redis_client.setex(
        f"{JOB_KEY_PREFIX}{job_id}", JOB_TTL, json.dumps(status_data)
    )

    # キューの末尾にジョブを追加
    redis_client.rpush(JOB_QUEUE_KEY, json.dumps(job_payload))

    return job_id


def get_job_status(redis_client, job_id: str) -> dict | None:
    """ジョブのステータス・結果を取得する"""
    data = redis_client.get(f"{JOB_KEY_PREFIX}{job_id}")
    return json.loads(data) if data else None


def set_job_processing(redis_client, job_id: str) -> None:
    """ジョブを処理中に更新する"""
    data = redis_client.get(f"{JOB_KEY_PREFIX}{job_id}")
    status_data = json.loads(data) if data else {}
    status_data.update(
        {
            "status": "processing",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    redis_client.setex(
        f"{JOB_KEY_PREFIX}{job_id}", JOB_TTL, json.dumps(status_data)
    )


def set_job_completed(redis_client, job_id: str, result: Any) -> None:
    """ジョブを完了に更新し結果を保存する"""
    data = redis_client.get(f"{JOB_KEY_PREFIX}{job_id}")
    status_data = json.loads(data) if data else {}
    status_data.update(
        {
            "status": "completed",
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "result": result,
        }
    )
    redis_client.setex(
        f"{JOB_KEY_PREFIX}{job_id}", JOB_TTL, json.dumps(status_data)
    )


def set_job_failed(redis_client, job_id: str, error: str) -> None:
    """ジョブを失敗に更新する"""
    data = redis_client.get(f"{JOB_KEY_PREFIX}{job_id}")
    status_data = json.loads(data) if data else {}
    status_data.update(
        {
            "status": "failed",
            "failed_at": datetime.now(timezone.utc).isoformat(),
            "error": error,
        }
    )
    redis_client.setex(
        f"{JOB_KEY_PREFIX}{job_id}", JOB_TTL, json.dumps(status_data)
    )
