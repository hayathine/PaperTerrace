"""
Storage Provider abstraction layer.
Supports SQLite (current) and Cloud SQL/GCS (future GCP deployment).
"""

import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from dotenv import load_dotenv

from src.logger import logger

load_dotenv()

DB_PATH = os.getenv("DB_PATH", "ocr_reader.db")


class StorageInterface(ABC):
    """Abstract interface for storage providers."""

    @abstractmethod
    def init_tables(self) -> None:
        """Initialize required database tables."""
        ...

    @abstractmethod
    def save_paper(
        self,
        paper_id: str,
        file_hash: str,
        filename: str,
        ocr_text: str,
        html_content: str,
        target_language: str,
    ) -> str:
        """Save a paper to storage. Returns paper_id."""
        ...

    @abstractmethod
    def get_paper(self, paper_id: str) -> dict | None:
        """Get a paper by ID."""
        ...

    @abstractmethod
    def get_paper_by_hash(self, file_hash: str) -> dict | None:
        """Get a paper by file hash."""
        ...

    @abstractmethod
    def list_papers(self, limit: int = 50) -> list[dict]:
        """List recent papers."""
        ...

    @abstractmethod
    def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper by ID."""
        ...

    @abstractmethod
    def save_memo(
        self, memo_id: str, session_id: str, term: str, note: str
    ) -> str:
        """Save a memo. Returns memo_id."""
        ...

    @abstractmethod
    def get_memos(self, session_id: str) -> list[dict]:
        """Get all memos for a session."""
        ...

    @abstractmethod
    def delete_memo(self, memo_id: str) -> bool:
        """Delete a memo by ID."""
        ...


class SQLiteStorage(StorageInterface):
    """SQLite storage implementation."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_tables()
        logger.info(f"SQLiteStorage initialized with db: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_tables(self) -> None:
        """Initialize required database tables."""
        with self._get_connection() as conn:
            # Papers table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS papers (
                    paper_id TEXT PRIMARY KEY,
                    file_hash TEXT UNIQUE,
                    filename TEXT,
                    ocr_text TEXT,
                    html_content TEXT,
                    target_language TEXT DEFAULT 'ja',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # OCR cache table (existing)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ocr_reader (
                    file_hash TEXT PRIMARY KEY,
                    filename TEXT,
                    ocr_text TEXT,
                    model_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Memos table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memos (
                    memo_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    term TEXT,
                    note TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def save_paper(
        self,
        paper_id: str,
        file_hash: str,
        filename: str,
        ocr_text: str,
        html_content: str,
        target_language: str = "ja",
    ) -> str:
        """Save a paper to storage."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO papers 
                (paper_id, file_hash, filename, ocr_text, html_content, target_language, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    file_hash,
                    filename,
                    ocr_text,
                    html_content,
                    target_language,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        logger.info(f"Paper saved: {paper_id} ({filename})")
        return paper_id

    def get_paper(self, paper_id: str) -> dict | None:
        """Get a paper by ID."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE paper_id = ?", (paper_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_paper_by_hash(self, file_hash: str) -> dict | None:
        """Get a paper by file hash."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM papers WHERE file_hash = ?", (file_hash,)
            ).fetchone()
            return dict(row) if row else None

    def list_papers(self, limit: int = 50) -> list[dict]:
        """List recent papers."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT paper_id, filename, target_language, created_at FROM papers ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM papers WHERE paper_id = ?", (paper_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Paper deleted: {paper_id}")
            return deleted

    def save_memo(
        self, memo_id: str, session_id: str, term: str, note: str
    ) -> str:
        """Save a memo."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO memos (memo_id, session_id, term, note, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (memo_id, session_id, term, note, datetime.now().isoformat()),
            )
            conn.commit()
        logger.info(f"Memo saved: {memo_id}")
        return memo_id

    def get_memos(self, session_id: str) -> list[dict]:
        """Get all memos for a session."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM memos WHERE session_id = ? ORDER BY created_at DESC",
                (session_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_memo(self, memo_id: str) -> bool:
        """Delete a memo by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "DELETE FROM memos WHERE memo_id = ?", (memo_id,)
            )
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Memo deleted: {memo_id}")
            return deleted


class CloudSQLStorage(StorageInterface):
    """
    Cloud SQL storage implementation (stub for future GCP deployment).
    
    To use Cloud SQL, set:
    - STORAGE_PROVIDER=cloudsql
    - CLOUDSQL_CONNECTION_NAME=project:region:instance
    - DB_USER, DB_PASSWORD, DB_NAME
    """

    def __init__(self):
        self.connection_name = os.getenv("CLOUDSQL_CONNECTION_NAME")
        logger.info(
            f"CloudSQLStorage initialized (stub) - connection: {self.connection_name}"
        )

    def init_tables(self) -> None:
        raise NotImplementedError("CloudSQLStorage is a stub.")

    def save_paper(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError("CloudSQLStorage is a stub.")

    def get_paper(self, paper_id: str) -> dict | None:
        raise NotImplementedError("CloudSQLStorage is a stub.")

    def get_paper_by_hash(self, file_hash: str) -> dict | None:
        raise NotImplementedError("CloudSQLStorage is a stub.")

    def list_papers(self, limit: int = 50) -> list[dict]:
        raise NotImplementedError("CloudSQLStorage is a stub.")

    def delete_paper(self, paper_id: str) -> bool:
        raise NotImplementedError("CloudSQLStorage is a stub.")

    def save_memo(self, *args: Any, **kwargs: Any) -> str:
        raise NotImplementedError("CloudSQLStorage is a stub.")

    def get_memos(self, session_id: str) -> list[dict]:
        raise NotImplementedError("CloudSQLStorage is a stub.")

    def delete_memo(self, memo_id: str) -> bool:
        raise NotImplementedError("CloudSQLStorage is a stub.")


def get_storage_provider() -> StorageInterface:
    """
    Factory function to get the configured storage provider.
    
    Set STORAGE_PROVIDER environment variable:
    - "sqlite" (default): Use local SQLite
    - "cloudsql": Use Cloud SQL (requires GCP setup)
    """
    provider_type = os.getenv("STORAGE_PROVIDER", "sqlite").lower()

    if provider_type == "cloudsql":
        return CloudSQLStorage()
    return SQLiteStorage()
