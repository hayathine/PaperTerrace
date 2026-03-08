"""
BigQuery Logging Client - Singleton client for behavioral log storage.
Replaces CloudSQL for: dspy_traces, trajectories, feedback.
Environment-aware dataset selection (prod/dev).
"""

import os
import threading

from google.cloud import bigquery

from app.core.config import get_bq_log_dataset
from common.logger import ServiceLogger

log = ServiceLogger("BigQueryLog")


class BigQueryLogClient:
    """Thread-safe singleton BigQuery client for behavioral logs."""

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "BigQueryLogClient":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.project_id = os.getenv("GCP_PROJECT_ID", "gen-lang-client-0800253336")
        self.dataset_id = get_bq_log_dataset()
        self.client = bigquery.Client(project=self.project_id)
        log.info(
            "init",
            f"BigQuery client initialized: {self.project_id}.{self.dataset_id}",
        )

    def table_ref(self, table_name: str) -> str:
        return f"{self.project_id}.{self.dataset_id}.{table_name}"

    def streaming_insert(self, table_name: str, rows: list[dict]) -> None:
        """Insert rows via streaming API (fast, near real-time)."""
        ref = self.table_ref(table_name)
        errors = self.client.insert_rows_json(ref, rows)
        if errors:
            log.error("streaming_insert", f"Errors: {errors}", table=table_name)
            raise RuntimeError(f"BigQuery streaming insert errors: {errors}")

    def query(self, sql: str, params: list | None = None):
        """Execute a SQL query and return results iterator."""
        job_config = bigquery.QueryJobConfig()
        if params:
            job_config.query_parameters = params
        return self.client.query(sql, job_config=job_config).result()

    def query_one(self, sql: str, params: list | None = None):
        """Execute a query and return the first row, or None."""
        results = self.query(sql, params)
        return next(iter(results), None)

    def execute_dml(self, sql: str, params: list | None = None) -> int:
        """Execute a DML statement. Returns number of affected rows."""
        job_config = bigquery.QueryJobConfig()
        if params:
            job_config.query_parameters = params
        job = self.client.query(sql, job_config=job_config)
        job.result()  # Wait for completion
        return job.num_dml_affected_rows or 0
