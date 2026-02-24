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

from common.logger import configure_logging, logger

# Configure logging
configure_logging()


class QueueWorker:
    """Background job processor using Redis as queue."""

    def __init__(self):
        # self.redis_host = os.getenv("REDIS_HOST", "localhost")
        # self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.redis = None
        self.running = False

    def connect(self):
        """Connect to Redis."""
        logger.info(f"Attempting to connect to Redis using URL: {self.redis_url}")
        try:
            self.redis = Redis.from_url(self.redis_url, socket_connect_timeout=2)
            self.redis.ping()
            logger.info(f"Connected to Redis at {self.redis_url}")
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
        job_id = job_data.get("id", "unknown")

        logger.info(f"Processing job {job_id} of type {job_type}")

        try:
            if job_type == "pdf_processing":
                await self.process_pdf_job(job_data)
            elif job_type == "batch_operation":
                await self.process_batch_job(job_data)
            else:
                logger.warning(f"Unknown job type: {job_type}")

            logger.info(f"Job {job_id} completed successfully")

        except Exception as e:
            logger.error(f"Job {job_id} failed: {e}")
            logger.error(traceback.format_exc())
            # Optionally requeue or move to dead letter queue
            self.handle_job_failure(job_id, job_data, str(e))

    async def process_pdf_job(self, job_data: dict):
        """
        Process PDF analysis job.

        Args:
            job_data: Job data with PDF file information
        """
        # Import here to avoid circular dependencies

        # pdf_service = PDFService()

        file_path = job_data.get("file_path")
        user_id = job_data.get("user_id")
        session_id = job_data.get("session_id")
        # lang = job_data.get("lang", "ja")

        logger.info(
            f"Processing PDF: {file_path} for user {user_id}, session {session_id}"
        )

        # Process PDF (implementation depends on your PDFService)
        # This is a placeholder - adjust based on your actual implementation
        # result = await pdf_service.analyze_pdf(file_path, lang)

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

        # Process batch operation
        for item in items:
            try:
                # Process individual item
                logger.debug(f"Processing item: {item}")
                # Add your batch processing logic here
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
        # Store failed job for later inspection
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
        logger.info("Queue worker started")

        while self.running:
            try:
                # Block for up to 5 seconds waiting for a job
                result = self.redis.blpop("job_queue", timeout=5)

                if result:
                    queue_name, job_json = result
                    job_data = json.loads(job_json)
                    await self.process_job(job_data)
                else:
                    # No job available, continue loop
                    await asyncio.sleep(0.1)

            except KeyboardInterrupt:
                logger.info("Received shutdown signal")
                self.running = False
                break
            except Exception as e:
                logger.error(f"Worker error: {e}")
                logger.error(traceback.format_exc())
                # Wait before retrying
                await asyncio.sleep(5)

        logger.info("Queue worker stopped")

    def stop(self):
        """Stop the worker."""
        self.running = False


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
