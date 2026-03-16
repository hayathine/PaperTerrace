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
JOB_PUB_PREFIX = "layout_job_pub:"

# ジョブステータスのアトミック更新用 Lua スクリプト
# KEYS[1]: ジョブキー, ARGV[1]: TTL秒, ARGV[2]: JSON形式の更新フィールド
_ATOMIC_UPDATE_SCRIPT = """
local key = KEYS[1]
local ttl = tonumber(ARGV[1])
local updates = cjson.decode(ARGV[2])
local current = {}
local data = redis.call('GET', key)
if data then
    current = cjson.decode(data)
end
for k, v in pairs(updates) do
    current[k] = v
end
redis.call('SETEX', key, ttl, cjson.encode(current))
return 1
"""


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
        "type": "layout_analysis",
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


def _atomic_update(redis_client, job_id: str, updates: dict) -> None:
    """Lua スクリプトでジョブデータをアトミックに更新する。
    失敗時は read-modify-write フォールバックを使用する。
    """
    key = f"{JOB_KEY_PREFIX}{job_id}"
    try:
        redis_client.eval(_ATOMIC_UPDATE_SCRIPT, 1, key, JOB_TTL, json.dumps(updates))
    except Exception:
        # Lua 非対応環境や一時エラー時のフォールバック
        data = redis_client.get(key)
        status_data = json.loads(data) if data else {}
        status_data.update(updates)
        redis_client.setex(key, JOB_TTL, json.dumps(status_data))


def set_job_processing(redis_client, job_id: str) -> None:
    """ジョブを処理中に更新する"""
    _atomic_update(redis_client, job_id, {
        "status": "processing",
        "started_at": datetime.now(timezone.utc).isoformat(),
    })


def set_job_completed(redis_client, job_id: str, result: Any) -> None:
    """ジョブを完了に更新し結果を保存する"""
    updates = {
        "status": "completed",
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "result": result,
    }
    _atomic_update(redis_client, job_id, updates)
    # Pub/Sub で完了を通知（失敗しても問題なし）
    try:
        redis_client.publish(
            f"{JOB_PUB_PREFIX}{job_id}",
            json.dumps({"status": "completed", "result": result}),
        )
    except Exception:
        pass


def set_job_failed(redis_client, job_id: str, error: str) -> None:
    """ジョブを失敗に更新する"""
    updates = {
        "status": "failed",
        "failed_at": datetime.now(timezone.utc).isoformat(),
        "error": error,
    }
    _atomic_update(redis_client, job_id, updates)
    # Pub/Sub で失敗を通知（失敗しても問題なし）
    try:
        redis_client.publish(
            f"{JOB_PUB_PREFIX}{job_id}",
            json.dumps({"status": "failed", "error": error}),
        )
    except Exception:
        pass
