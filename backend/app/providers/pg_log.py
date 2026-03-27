"""
PostgreSQL Log Client - ログDB（vostro ポッド）への接続クライアント。
BigQueryLogClient の置き換え。環境に応じた LOG_DATABASE_URL に接続する。
"""

import threading

from sqlalchemy import create_engine, text
from sqlalchemy.pool import QueuePool

from app.core.config import get_log_database_url, get_log_schema
from common.logger import ServiceLogger

log = ServiceLogger("PgLog")

_LOG_SCHEMA = get_log_schema()


class PgLogClient:
    """Thread-safe singleton PostgreSQL client for behavioral logs."""

    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "PgLogClient":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        url = get_log_database_url()
        self.engine = create_engine(
            url,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
        )
        log.info("init", f"PgLog client initialized (schema={_LOG_SCHEMA})")

    def table_ref(self, table_name: str) -> str:
        return f"{_LOG_SCHEMA}.{table_name}"

    def insert(self, table: str, rows: list[dict]) -> None:
        """複数行を一括 INSERT する。"""
        if not rows:
            return
        cols = list(rows[0].keys())
        col_str = ", ".join(cols)
        placeholders = ", ".join(f":{c}" for c in cols)
        sql = text(f"INSERT INTO {_LOG_SCHEMA}.{table} ({col_str}) VALUES ({placeholders})")
        try:
            with self.engine.connect() as conn:
                conn.execute(sql, rows)
                conn.commit()
        except Exception as e:
            log.error("insert", f"Failed to insert into {table}: {e}")
            raise

    def query(self, sql: str, params: dict | None = None) -> list[dict]:
        """SELECT クエリを実行してリストで返す。"""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            return [dict(row) for row in result.mappings()]

    def query_one(self, sql: str, params: dict | None = None) -> dict | None:
        """SELECT クエリを実行して最初の行を返す。なければ None。"""
        rows = self.query(sql, params)
        return rows[0] if rows else None

    def execute_dml(self, sql: str, params: dict | None = None) -> int:
        """UPDATE/DELETE を実行して影響行数を返す。"""
        with self.engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            conn.commit()
            return result.rowcount
