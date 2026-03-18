"""
Queue Worker for PaperTerrace
Processes background jobs from Redis queue.
"""

import asyncio
import json
import os
import traceback
from datetime import datetime

from redis import Redis

from common.config import settings

from app.domain.services.layout_analysis_service import LayoutAnalysisService
from app.workers.layout_job import (
    JOB_QUEUE_KEY,
    publish_job_figures,
    set_job_completed,
    set_job_failed,
    set_job_processing,
)
from common.logger import configure_logging, logger

# Configure logging
configure_logging()


class QueueWorker:
    """Background job processor using Redis as queue."""

    def __init__(self):
        self.redis_url = settings.get("REDIS_URL", "redis://redis:6379/0")
        self.redis = None
        self.running = False

    def connect(self):
        """Connect to Redis."""
        logger.info(f"Attempting to connect to Redis using URL: {self.redis_url}")
        try:
            self.redis = Redis.from_url(self.redis_url, socket_connect_timeout=2)
            self.redis.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
            open("/tmp/ready", "w").close()
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def process_job(self, job_data: dict):
        """
        Process a single job.

        Args:
            job_data: Job data dictionary with 'type' and other fields
        """
        job_type = job_data.get("type")
        job_id = job_data.get("job_id", job_data.get("id", "unknown"))

        logger.info(f"Processing job {job_id} of type {job_type}")

        try:
            if job_type == "layout_analysis":
                await self.process_layout_job(job_data)
            elif job_type == "pdf_processing":
                await self.process_pdf_job(job_data)
            elif job_type == "batch_operation":
                await self.process_batch_job(job_data)
            else:
                logger.warning(f"Unknown job type: {job_type}")
                return

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            logger.error(traceback.format_exc())
            self.handle_job_failure(job_id, job_data, str(e))

    async def process_layout_job(self, job_data: dict):
        """
        レイアウト解析ジョブを処理する。

        Args:
            job_data: paper_id, page_numbers, user_id, file_hash, session_id を含む辞書
        """
        job_id = job_data.get("job_id", "unknown")
        paper_id = job_data.get("paper_id")
        page_numbers = job_data.get("page_numbers")
        user_id = job_data.get("user_id")
        file_hash = job_data.get("file_hash")
        session_id = job_data.get("session_id")

        logger.info(
            f"[layout_job] Starting layout analysis: job={job_id}, paper={paper_id}, pages={page_numbers}"
        )

        set_job_processing(self.redis, job_id)

        async def _on_figures(batch: list) -> None:
            publish_job_figures(self.redis, job_id, batch)

        service = LayoutAnalysisService()
        figures = await service.analyze_layout_lazy(
            paper_id=paper_id,
            page_numbers=page_numbers,
            user_id=user_id,
            file_hash=file_hash,
            session_id=session_id,
            on_figures=_on_figures,
        )

        set_job_completed(self.redis, job_id, figures)
        logger.info(
            f"[layout_job] Completed: job={job_id}, figures={len(figures)}"
        )

    async def process_pdf_job(self, job_data: dict):
        """
        Process PDF analysis job.

        Args:
            job_data: Job data with PDF file information
        """
        file_path = job_data.get("file_path")
        user_id = job_data.get("user_id")
        session_id = job_data.get("session_id")

        logger.info(
            f"Processing PDF: {file_path} for user {user_id}, session {session_id}"
        )
        logger.info(f"PDF processing completed for {file_path}")

    async def process_batch_job(self, job_data: dict):
        """
        Process batch operation job.

        Args:
            job_data: Job data with batch operation details
        """
        operation = job_data.get("operation")
        items = job_data.get("items", [])

        logger.info(f"Processing batch operation: {operation} with {len(items)} items")

        for item in items:
            try:
                logger.debug(f"Processing item: {item}")
            except Exception as e:
                logger.error(f"Failed to process item {item}: {e}")

        logger.info(f"Batch operation {operation} completed")

    def handle_job_failure(self, job_id: str, job_data: dict, error: str):
        """
        Handle job failure.

        Args:
            job_id: Job identifier
            job_data: Original job data
            error: Error message
        """
        # layout_analysis ジョブはステータスキーに失敗を記録
        if job_data.get("type") == "layout_analysis":
            try:
                set_job_failed(self.redis, job_id, error)
            except Exception as e:
                logger.error(f"Failed to update job status: {e}")

        # 失敗ジョブを dead letter queue に保存
        failed_job = {
            "id": job_id,
            "data": job_data,
            "error": error,
            "failed_at": datetime.now().isoformat(),
        }

        try:
            self.redis.lpush("failed_jobs", json.dumps(failed_job))
            logger.info(f"Job {job_id} moved to failed jobs queue")
        except Exception as e:
            logger.error(f"Failed to store failed job: {e}")

    async def run(self):
        """Main worker loop."""
        self.running = True
        logger.info(f"Queue worker started, listening on: {JOB_QUEUE_KEY}")

        while self.running:
            try:
                # blpop はブロッキング呼び出しのためスレッドで実行してイベントループを解放する
                result = await asyncio.to_thread(
                    self.redis.blpop, JOB_QUEUE_KEY, 5
                )

                if result:
                    _, job_json = result
                    job_data = json.loads(job_json)
                    await self.process_job(job_data)
                else:
                    # タイムアウト（ジョブなし）: すぐ次のループへ
                    await asyncio.sleep(0)

            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                logger.error(traceback.format_exc())
                # エラー時はバックオフして再試行
                await asyncio.sleep(5)

        logger.info("Queue worker stopped")

    def stop(self):
        """Stop the worker."""
        self.running = False
        try:
            os.remove("/tmp/ready")
        except FileNotFoundError:
            pass


async def main():
    """Main entry point for queue worker."""
    worker = QueueWorker()

    try:
        worker.connect()
        await worker.run()
    except KeyboardInterrupt:
        logger.info("Shutting down gracefully...")
        worker.stop()
    except Exception as e:
        logger.error(f"Worker failed: {e}")
        logger.error(traceback.format_exc())
        raise


if __name__ == "__main__":
    asyncio.run(main())
