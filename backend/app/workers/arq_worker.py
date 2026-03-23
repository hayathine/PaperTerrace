"""
ARQ ワーカー設定

ARQ (Async Redis Queue) を使用したバックグラウンドジョブ処理。
自動リトライ・タイムアウト・並行数制御を ARQ に委任する。
"""

import redis as sync_redis_lib
from arq.connections import RedisSettings

from app.domain.services.layout_analysis_service import LayoutAnalysisService
from app.workers.layout_job import (
    publish_job_figures,
    set_job_completed,
    set_job_failed,
    set_job_processing,
)
from app.core.config import get_redis_url
from common.logger import configure_logging, logger

configure_logging()

MAX_RETRIES = 3
JOB_TIMEOUT = 600  # 10分


async def process_layout_analysis(
    ctx: dict,
    job_id: str,
    paper_id: str,
    page_numbers: list[int] | None,
    user_id: str | None,
    file_hash: str | None,
    session_id: str | None,
) -> None:
    """
    レイアウト解析ジョブを処理する。

    ARQ により自動リトライされる（最大 MAX_RETRIES 回）。
    最終リトライでも失敗した場合のみ、ジョブステータスを "failed" に更新する。
    """

    sync_redis = ctx["sync_redis"]
    job_try: int = ctx["job_try"]
    is_last_try = job_try >= MAX_RETRIES

    logger.info(
        f"[arq] Starting layout analysis: job={job_id}, paper={paper_id}, "
        f"pages={page_numbers}, try={job_try}/{MAX_RETRIES}"
    )

    set_job_processing(sync_redis, job_id)

    async def _on_figures(batch: list) -> None:
        publish_job_figures(sync_redis, job_id, batch)

    try:
        service = LayoutAnalysisService()
        figures = await service.analyze_layout_lazy(
            paper_id=paper_id,
            page_numbers=page_numbers,
            user_id=user_id,
            file_hash=file_hash,
            session_id=session_id,
            on_figures=_on_figures,
        )
        set_job_completed(sync_redis, job_id, figures)
        logger.info(f"[arq] Completed: job={job_id}, figures={len(figures)}")

    except Exception as e:
        logger.error(f"[arq] Job failed: job={job_id}, try={job_try}, error={e}")
        if is_last_try:
            # 最終リトライ失敗時のみ failed に更新（途中リトライ時は SSE に失敗を流さない）
            set_job_failed(sync_redis, job_id, str(e))
        raise  # ARQ にリトライを委ねる


async def startup(ctx: dict) -> None:
    """ワーカー起動時の初期化処理。"""
    ctx["sync_redis"] = sync_redis_lib.Redis.from_url(
        get_redis_url(),
        decode_responses=True,
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
    )
    # readiness probe 用ファイル（Helm の exec probe と連携）
    open("/tmp/ready", "w").close()  # noqa: SIM115
    logger.info("[arq] Worker started")


async def shutdown(ctx: dict) -> None:
    """ワーカー終了時のクリーンアップ処理。"""
    if "sync_redis" in ctx:
        ctx["sync_redis"].close()
    import os
    try:
        os.remove("/tmp/ready")
    except FileNotFoundError:
        pass
    logger.info("[arq] Worker stopped")


class WorkerSettings:
    """ARQ ワーカー設定。"""

    functions = [process_layout_analysis]
    on_startup = startup
    on_shutdown = shutdown

    redis_settings = RedisSettings.from_dsn(get_redis_url())

    max_jobs = 3          # Pod 1台あたりの同時処理ジョブ数
    job_timeout = JOB_TIMEOUT
    max_tries = MAX_RETRIES
    retry_delay = 30      # リトライ間隔（秒）
    poll_delay = 0.3      # キュー確認間隔（デフォルト0.5秒）

    # 完了ジョブ結果の保持時間（layout_job TTL と合わせる）
    keep_result_s = 3600
    keep_result_forever = False
