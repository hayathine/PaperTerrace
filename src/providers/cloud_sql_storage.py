"""
Cloud SQL Storage Provider
"""

import json
import os
from datetime import datetime

import psycopg2
from dotenv import load_dotenv
from psycopg2.extras import RealDictCursor

from src.logger import logger

from .storage_provider import StorageInterface

load_dotenv()


class CloudSQLStorage(StorageInterface):
    """
    Cloud SQL storage implementation using psycopg2.
    """

    def __init__(self):
        self.db_user = os.getenv("DB_USER")
        self.db_password = os.getenv("DB_PASSWORD")
        self.db_name = os.getenv("DB_NAME")
        # Cloud Run uses Unix socket default, or TCP for local
        self.host = os.getenv("DB_HOST", "127.0.0.1")
        self.port = os.getenv("DB_PORT", "5432")
        self.instance_connection_name = os.getenv("CLOUDSQL_CONNECTION_NAME")

        logger.info(f"CloudSQLStorage initialized - host: {self.host}, db: {self.db_name}")

    def _get_connection(self):
        try:
            if self.instance_connection_name and self.host.startswith("/"):
                # Unix socket connection (Cloud Run)
                dsn = f"dbname='{self.db_name}' user='{self.db_user}' password='{self.db_password}' host='{self.host}/{self.instance_connection_name}'"
            else:
                # TCP connection
                dsn = f"dbname='{self.db_name}' user='{self.db_user}' password='{self.db_password}' host='{self.host}' port='{self.port}'"

            conn = psycopg2.connect(dsn)
            return conn
        except Exception as e:
            logger.error(f"Failed to connect to Cloud SQL: {e}")
            raise

    def init_tables(self) -> None:
        """Initialize required database tables."""
        # Note: In production, use migration tools like Alembic.
        # This is a basic schema init for compatibility.
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                # Users table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS users (
                        id TEXT PRIMARY KEY,
                        email TEXT UNIQUE NOT NULL,
                        display_name TEXT,
                        affiliation TEXT,
                        bio TEXT,
                        research_fields TEXT,
                        profile_image_url TEXT,
                        is_public INTEGER DEFAULT 1,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Papers table
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS papers (
                        paper_id TEXT PRIMARY KEY,
                        file_hash TEXT UNIQUE,
                        filename TEXT,
                        ocr_text TEXT,
                        html_content TEXT,
                        target_language TEXT DEFAULT 'ja',
                        owner_id TEXT,
                        visibility TEXT DEFAULT 'private',
                        title TEXT,
                        authors TEXT,
                        abstract TEXT,
                        tags TEXT,
                        view_count INTEGER DEFAULT 0,
                        like_count INTEGER DEFAULT 0,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Paper likes
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS paper_likes (
                        user_id TEXT,
                        paper_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        PRIMARY KEY (user_id, paper_id)
                    )
                """)
                # OCR cache
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS ocr_reader (
                        file_hash TEXT PRIMARY KEY,
                        filename TEXT,
                        ocr_text TEXT,
                        model_name TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Notes
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS notes (
                        note_id TEXT PRIMARY KEY,
                        session_id TEXT,
                        term TEXT,
                        note TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Paper Stamps
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS paper_stamps (
                        id TEXT PRIMARY KEY,
                        paper_id TEXT REFERENCES papers(paper_id) ON DELETE CASCADE,
                        user_id TEXT,
                        stamp_type TEXT,
                        page_number INTEGER,
                        x REAL,
                        y REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                # Note Stamps
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS note_stamps (
                        id TEXT PRIMARY KEY,
                        note_id TEXT REFERENCES notes(note_id) ON DELETE CASCADE,
                        user_id TEXT,
                        stamp_type TEXT,
                        x REAL,
                        y REAL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
            conn.commit()

    # ===== Paper methods =====

    def save_paper(
        self,
        paper_id: str,
        file_hash: str,
        filename: str,
        ocr_text: str,
        html_content: str,
        target_language: str = "ja",
        owner_id: str | None = None,
        visibility: str = "private",
    ) -> str:
        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO papers 
                    (paper_id, file_hash, filename, ocr_text, html_content, target_language, 
                     owner_id, visibility, title, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (paper_id) DO UPDATE SET
                    file_hash = EXCLUDED.file_hash,
                    filename = EXCLUDED.filename,
                    ocr_text = EXCLUDED.ocr_text,
                    html_content = EXCLUDED.html_content,
                    target_language = EXCLUDED.target_language,
                    owner_id = EXCLUDED.owner_id,
                    visibility = EXCLUDED.visibility,
                    title = EXCLUDED.title,
                    updated_at = EXCLUDED.updated_at
                    """,
                    (
                        paper_id,
                        file_hash,
                        filename,
                        ocr_text,
                        html_content,
                        target_language,
                        owner_id,
                        visibility,
                        filename,
                        now,
                        now,
                    ),
                )
            conn.commit()
        logger.info(f"Paper saved (CloudSQL): {paper_id}")
        return paper_id

    def get_paper(self, paper_id: str) -> dict | None:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM papers WHERE paper_id = %s", (paper_id,))
                row = cur.fetchone()
                if row:
                    data = dict(row)
                    if data.get("tags"):
                        try:
                            data["tags"] = json.loads(data["tags"])
                        except json.JSONDecodeError:
                            data["tags"] = []
                    return data
                return None

    def get_paper_by_hash(self, file_hash: str) -> dict | None:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM papers WHERE file_hash = %s", (file_hash,))
                row = cur.fetchone()
                return dict(row) if row else None

    def list_papers(self, limit: int = 50) -> list[dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT paper_id, filename, target_language, owner_id, visibility, created_at 
                       FROM papers ORDER BY created_at DESC LIMIT %s""",
                    (limit,),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def update_paper_html(self, paper_id: str, html_content: str) -> bool:
        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE papers SET html_content = %s, updated_at = %s WHERE paper_id = %s",
                    (html_content, now, paper_id),
                )
                conn.commit()
                return cur.rowcount > 0

    def delete_paper(self, paper_id: str) -> bool:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM papers WHERE paper_id = %s", (paper_id,))
            conn.commit()
            return cur.rowcount > 0

    def update_paper_visibility(self, paper_id: str, visibility: str) -> bool:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE papers SET visibility = %s, updated_at = %s WHERE paper_id = %s",
                    (visibility, datetime.now(), paper_id),
                )
            conn.commit()
            return cur.rowcount > 0

    # ===== Note methods =====

    def save_note(
        self,
        note_id: str,
        session_id: str,
        term: str,
        note: str,
        image_url: str | None = None,
    ) -> str:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notes (note_id, session_id, term, note, image_url, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (note_id, session_id, term, note, image_url, datetime.now()),
                )
            conn.commit()
        return note_id

    def get_notes(self, session_id: str) -> list[dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM notes WHERE session_id = %s ORDER BY created_at DESC",
                    (session_id,),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def delete_note(self, note_id: str) -> bool:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM notes WHERE note_id = %s", (note_id,))
            conn.commit()
            return cur.rowcount > 0

    # ===== Stamp methods =====

    def add_paper_stamp(
        self,
        paper_id: str,
        stamp_type: str,
        user_id: str | None = None,
        page_number: int | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> str:
        import uuid6

        stamp_id = str(uuid6.uuid7())
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO paper_stamps (id, paper_id, user_id, stamp_type, page_number, x, y, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (stamp_id, paper_id, user_id, stamp_type, page_number, x, y, datetime.now()),
                )
            conn.commit()
        return stamp_id

    def get_paper_stamps(self, paper_id: str) -> list[dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM paper_stamps WHERE paper_id = %s ORDER BY created_at DESC",
                    (paper_id,),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def delete_paper_stamp(self, stamp_id: str) -> bool:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM paper_stamps WHERE id = %s", (stamp_id,))
            conn.commit()
            return cur.rowcount > 0

    def add_note_stamp(
        self,
        note_id: str,
        stamp_type: str,
        user_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> str:
        import uuid6

        stamp_id = str(uuid6.uuid7())
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO note_stamps (id, note_id, user_id, stamp_type, x, y, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (stamp_id, note_id, user_id, stamp_type, x, y, datetime.now()),
                )
            conn.commit()
        return stamp_id

    def get_note_stamps(self, note_id: str) -> list[dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM note_stamps WHERE note_id = %s ORDER BY created_at DESC",
                    (note_id,),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows]

    def delete_note_stamp(self, stamp_id: str) -> bool:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM note_stamps WHERE id = %s", (stamp_id,))
            conn.commit()
            return cur.rowcount > 0

    # ===== User methods =====

    def create_user(self, user_data: dict) -> str:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, email, display_name, affiliation, bio, 
                                       research_fields, profile_image_url, is_public, 
                                       created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        user_data["id"],
                        user_data["email"],
                        user_data.get("display_name"),
                        user_data.get("affiliation"),
                        user_data.get("bio"),
                        json.dumps(user_data.get("research_fields", [])),
                        user_data.get("profile_image_url"),
                        1 if user_data.get("is_public", True) else 0,
                        user_data.get("created_at", datetime.now()),
                        user_data.get("updated_at", datetime.now()),
                    ),
                )
            conn.commit()
        return user_data["id"]

    def get_user(self, user_id: str) -> dict | None:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                row = cur.fetchone()
                if row:
                    data = dict(row)
                    data["is_public"] = bool(data.get("is_public", 1))
                    if data.get("research_fields"):
                        try:
                            # Postgres TEXT might come as string
                            if isinstance(data["research_fields"], str):
                                data["research_fields"] = json.loads(data["research_fields"])
                        except json.JSONDecodeError:
                            data["research_fields"] = []
                    else:
                        data["research_fields"] = []
                    return data
                return None

    def update_user(self, user_id: str, data: dict) -> bool:
        fields = []
        values = []
        for key, value in data.items():
            if key in ["id", "created_at"]:
                continue
            if key == "research_fields" and isinstance(value, list):
                value = json.dumps(value)
            if key == "is_public":
                value = 1 if value else 0
            fields.append(f"{key} = %s")
            values.append(value)

        if not fields:
            return False

        values.append(user_id)
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = %s", values)
            conn.commit()
            return cur.rowcount > 0

    def delete_user(self, user_id: str) -> bool:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
            conn.commit()
            return cur.rowcount > 0

    def get_user_stats(self, user_id: str) -> dict:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM papers WHERE owner_id = %s", (user_id,))
                total = cur.fetchone()[0]
                cur.execute(
                    "SELECT COUNT(*) FROM papers WHERE owner_id = %s AND visibility = 'public'",
                    (user_id,),
                )
                public = cur.fetchone()[0]
                cur.execute(
                    "SELECT COALESCE(SUM(view_count), 0) FROM papers WHERE owner_id = %s",
                    (user_id,),
                )
                views = cur.fetchone()[0]
                cur.execute(
                    "SELECT COALESCE(SUM(like_count), 0) FROM papers WHERE owner_id = %s",
                    (user_id,),
                )
                likes = cur.fetchone()[0]
                return {
                    "paper_count": total,
                    "public_paper_count": public,
                    "total_views": views,
                    "total_likes": likes,
                }

    def get_user_papers(
        self, user_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        offset = (page - 1) * per_page
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) FROM papers WHERE owner_id = %s", (user_id,))
                total = cur.fetchone()["count"]
                cur.execute(
                    """SELECT * FROM papers WHERE owner_id = %s 
                       ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (user_id, per_page, offset),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows], total

    def get_user_public_papers(
        self, user_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        offset = (page - 1) * per_page
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT COUNT(*) FROM papers WHERE owner_id = %s AND visibility = 'public'",
                    (user_id,),
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    """SELECT * FROM papers WHERE owner_id = %s AND visibility = 'public'
                       ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (user_id, per_page, offset),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows], total

    def get_public_papers(
        self, page: int = 1, per_page: int = 20, sort: str = "recent"
    ) -> tuple[list[dict], int]:
        offset = (page - 1) * per_page
        order_by = "created_at DESC"
        if sort == "popular":
            order_by = "view_count DESC"
        elif sort == "trending":
            order_by = "like_count DESC"

        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT COUNT(*) FROM papers WHERE visibility = 'public'")
                total = cur.fetchone()["count"]
                cur.execute(
                    f"""SELECT * FROM papers WHERE visibility = 'public'
                       ORDER BY {order_by} LIMIT %s OFFSET %s""",
                    (per_page, offset),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows], total

    def search_public_papers(
        self, query: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        offset = (page - 1) * per_page
        search_pattern = f"%{query}%"
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """SELECT COUNT(*) FROM papers 
                       WHERE visibility = 'public' 
                       AND (title LIKE %s OR authors LIKE %s OR abstract LIKE %s OR filename LIKE %s)""",
                    (search_pattern, search_pattern, search_pattern, search_pattern),
                )
                total = cur.fetchone()["count"]
                cur.execute(
                    """SELECT * FROM papers 
                       WHERE visibility = 'public' 
                       AND (title LIKE %s OR authors LIKE %s OR abstract LIKE %s OR filename LIKE %s)
                       ORDER BY created_at DESC LIMIT %s OFFSET %s""",
                    (
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        search_pattern,
                        per_page,
                        offset,
                    ),
                )
                rows = cur.fetchall()
                return [dict(row) for row in rows], total

    def get_popular_tags(self, limit: int = 20) -> list[dict]:
        return []

    def get_ocr_cache(self, file_hash: str) -> str | None:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT ocr_text FROM ocr_reader WHERE file_hash = %s", (file_hash,))
                row = cur.fetchone()
                if row:
                    return row[0]
                return None

    def save_ocr_cache(self, file_hash: str, ocr_text: str, filename: str, model_name: str) -> None:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO ocr_reader (file_hash, filename, ocr_text, model_name, created_at)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (file_hash) DO UPDATE SET
                    filename = EXCLUDED.filename,
                    ocr_text = EXCLUDED.ocr_text,
                    model_name = EXCLUDED.model_name
                    """,
                    (file_hash, filename, ocr_text, model_name, datetime.now()),
                )
            conn.commit()
