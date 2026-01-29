"""
Storage Provider abstraction layer.
Supports SQLite (current) and Cloud SQL/GCS (future GCP deployment).
"""

import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import datetime

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

    # ===== Paper methods =====

    @abstractmethod
    def save_paper(
        self,
        paper_id: str,
        file_hash: str,
        filename: str,
        ocr_text: str,
        html_content: str,
        target_language: str,
        layout_json: str | None = None,
        owner_id: str | None = None,
        visibility: str = "private",
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
    def update_paper_html(self, paper_id: str, html_content: str) -> bool:
        """Update the HTML content of a paper."""
        ...

    @abstractmethod
    def update_paper_abstract(self, paper_id: str, abstract: str) -> bool:
        """Update the abstract/summary of a paper."""
        ...

    @abstractmethod
    def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper by ID."""
        ...

    @abstractmethod
    def update_paper_visibility(self, paper_id: str, visibility: str) -> bool:
        """Update paper visibility."""
        ...

    # ===== Note methods =====

    @abstractmethod
    def save_note(
        self,
        note_id: str,
        session_id: str,
        term: str,
        note: str,
        image_url: str | None = None,
        page_number: int | None = None,
        x: float | None = None,
        y: float | None = None,
        user_id: str | None = None,
    ) -> str:
        """Save a note. Returns note_id."""
        ...

    @abstractmethod
    def get_notes(self, session_id: str, user_id: str | None = None) -> list[dict]:
        """Get all notes for a session or user."""
        ...

    @abstractmethod
    def delete_note(self, note_id: str) -> bool:
        """Delete a note by ID."""
        ...

    # ... (skipping stamp methods for brevity in this replacement block if possible, but replace_file_content replaces contiguous blocks) ...
    # Wait, I can't skip methods in the middle of a block. I should do it in chunks or be careful.
    # The Abstract methods are lines 76-94.

    # Let's do SQLiteStorage updates separately or together.
    # I'll update StorageInterface first.

    # ===== Stamp methods =====

    @abstractmethod
    def add_paper_stamp(
        self,
        paper_id: str,
        stamp_type: str,
        user_id: str | None = None,
        page_number: int | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> str:
        """Add a stamp to a paper with optional position."""
        ...

    @abstractmethod
    def get_paper_stamps(self, paper_id: str) -> list[dict]:
        """Get stamps for a paper."""
        ...

    @abstractmethod
    def delete_paper_stamp(self, stamp_id: str) -> bool:
        """Delete a stamp from a paper."""
        ...

    @abstractmethod
    def add_note_stamp(
        self,
        note_id: str,
        stamp_type: str,
        user_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> str:
        """Add a stamp to a note with optional position."""
        ...

    @abstractmethod
    def get_note_stamps(self, note_id: str) -> list[dict]:
        """Get stamps for a note."""
        ...

    @abstractmethod
    def delete_note_stamp(self, stamp_id: str) -> bool:
        """Delete a stamp from a note."""
        ...

    # ===== Figure methods =====

    @abstractmethod
    def save_figure(
        self,
        paper_id: str,
        page_number: int,
        bbox: list | tuple,
        image_url: str,
        caption: str = "",
        explanation: str = "",
    ) -> str:
        """Save a figure. Returns figure_id."""
        ...

    @abstractmethod
    def get_paper_figures(self, paper_id: str) -> list[dict]:
        """Get figures for a paper."""
        ...

    @abstractmethod
    def get_figure(self, figure_id: str) -> dict | None:
        """Get a figure by ID."""
        ...

    @abstractmethod
    def update_figure_explanation(self, figure_id: str, explanation: str) -> bool:
        """Update figure explanation."""
        ...

    # ===== User methods =====

    @abstractmethod
    def create_user(self, user_data: dict) -> str:
        """Create a new user. Returns user_id."""
        ...

    @abstractmethod
    def get_user(self, user_id: str) -> dict | None:
        """Get a user by ID."""
        ...

    @abstractmethod
    def update_user(self, user_id: str, data: dict) -> bool:
        """Update user data."""
        ...

    @abstractmethod
    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        ...

    @abstractmethod
    def get_user_stats(self, user_id: str) -> dict:
        """Get user statistics."""
        ...

    # ===== Social paper methods =====

    @abstractmethod
    def get_user_papers(
        self, user_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        """Get all papers for a user."""
        ...

    @abstractmethod
    def get_user_public_papers(
        self, user_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        """Get public papers for a user."""
        ...

    @abstractmethod
    def get_public_papers(
        self, page: int = 1, per_page: int = 20, sort: str = "recent"
    ) -> tuple[list[dict], int]:
        """Get all public papers for explore page."""
        ...

    @abstractmethod
    def search_public_papers(
        self, query: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        """Search public papers."""
        ...

    @abstractmethod
    def get_popular_tags(self, limit: int = 20) -> list[dict]:
        """Get popular tags."""
        ...

    @abstractmethod
    def get_ocr_cache(self, file_hash: str) -> str | None:
        """Get cached OCR text."""
        ...

    @abstractmethod
    def save_ocr_cache(self, file_hash: str, ocr_text: str, filename: str, model_name: str) -> None:
        """Save OCR text to cache."""
        ...

    @abstractmethod
    def save_session_context(self, session_id: str, paper_id: str) -> None:
        """Save session to paper mapping."""
        ...

    @abstractmethod
    def get_session_paper_id(self, session_id: str) -> str | None:
        """Get paper ID for a session."""
        ...


class SQLiteStorage(StorageInterface):
    """SQLite storage implementation."""

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_tables()
        self._migrate_tables()
        logger.info(f"SQLiteStorage initialized with db: {self.db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _migrate_tables(self) -> None:
        """Add missing columns to existing tables (handles schema migrations)."""
        with self._get_connection() as conn:
            # Get existing columns in papers table
            cursor = conn.execute("PRAGMA table_info(papers)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            # Define columns that should exist in papers table
            migrations = [
                ("owner_id", "TEXT"),
                ("visibility", "TEXT DEFAULT 'private'"),
                ("title", "TEXT"),
                ("authors", "TEXT"),
                ("abstract", "TEXT"),
                ("tags", "TEXT"),
                ("view_count", "INTEGER DEFAULT 0"),
                ("like_count", "INTEGER DEFAULT 0"),
                ("layout_json", "TEXT"),
                ("updated_at", "TIMESTAMP"),
                ("updated_at", "TIMESTAMP"),
            ]

            # Session table migration
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='app_sessions'"
            )
            if not cursor.fetchone():
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS app_sessions (
                        session_id TEXT PRIMARY KEY,
                        paper_id TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

            for column_name, column_type in migrations:
                if column_name not in existing_columns:
                    try:
                        conn.execute(f"ALTER TABLE papers ADD COLUMN {column_name} {column_type}")
                        logger.info(f"Added column '{column_name}' to papers table")
                    except sqlite3.OperationalError as e:
                        # Column might already exist, ignore
                        logger.debug(f"Column migration skipped: {e}")

            conn.commit()

            # Migrations for stamps and notes
            for table, columns in [
                (
                    "paper_stamps",
                    [
                        ("page_number", "INTEGER"),
                        ("x", "REAL"),
                        ("y", "REAL"),
                    ],
                ),
                (
                    "note_stamps",
                    [
                        ("x", "REAL"),
                        ("y", "REAL"),
                    ],
                ),
                (
                    "notes",
                    [
                        ("image_url", "TEXT"),
                        ("page_number", "INTEGER"),
                        ("x", "REAL"),
                        ("y", "REAL"),
                        ("user_id", "TEXT"),
                    ],
                ),
            ]:
                # Check if table exists first
                cursor = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table,)
                )
                if not cursor.fetchone():
                    continue

                cursor = conn.execute(f"PRAGMA table_info({table})")
                existing_cols = {row[1] for row in cursor.fetchall()}

                for col_name, col_type in columns:
                    if col_name not in existing_cols:
                        try:
                            # Use empty string default for non-null constraint issues if any,
                            # but here we allow nulls so it's fine.
                            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col_name} {col_type}")
                            logger.info(f"Added column '{col_name}' to {table}")
                        except sqlite3.OperationalError as e:
                            logger.warning(f"Failed to add column {col_name} to {table}: {e}")
            conn.commit()

    def init_tables(self) -> None:
        """Initialize required database tables."""
        with self._get_connection() as conn:
            # Users table
            conn.execute("""
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
            # Papers table (extended)
            conn.execute("""
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
                    layout_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Paper likes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_likes (
                    user_id TEXT,
                    paper_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, paper_id)
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
            # Notes table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS notes (
                    note_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    term TEXT,
                    note TEXT,
                    image_url TEXT,
                    user_id TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            # Paper Stamps table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_stamps (
                    id TEXT PRIMARY KEY,
                    paper_id TEXT,
                    user_id TEXT,
                    stamp_type TEXT,
                    page_number INTEGER,
                    x REAL,
                    y REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
                )
            """)
            # Note Stamps table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS note_stamps (
                    id TEXT PRIMARY KEY,
                    note_id TEXT,
                    user_id TEXT,
                    stamp_type TEXT,
                    x REAL,
                    y REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(note_id) REFERENCES notes(note_id) ON DELETE CASCADE
                )
            """)
            # Paper Figures table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS paper_figures (
                    id TEXT PRIMARY KEY,
                    paper_id TEXT,
                    page_number INTEGER,
                    bbox_json TEXT,
                    image_url TEXT,
                    caption TEXT,
                    explanation TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY(paper_id) REFERENCES papers(paper_id) ON DELETE CASCADE
                )
            """)
            # App Sessions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS app_sessions (
                    session_id TEXT PRIMARY KEY,
                    paper_id TEXT,
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
        layout_json: str | None = None,
        owner_id: str | None = None,
        visibility: str = "private",
    ) -> str:
        """Save a paper to storage."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO papers 
                (paper_id, file_hash, filename, ocr_text, html_content, target_language, 
                 layout_json, owner_id, visibility, title, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    paper_id,
                    file_hash,
                    filename,
                    ocr_text,
                    html_content,
                    target_language,
                    layout_json,
                    owner_id,
                    visibility,
                    filename,  # Use filename as default title
                    now,
                    now,
                ),
            )
            conn.commit()
        logger.info(f"Paper saved: {paper_id} ({filename})")
        return paper_id

    def get_paper(self, paper_id: str) -> dict | None:
        """Get a paper by ID."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM papers WHERE paper_id = ?", (paper_id,)).fetchone()
            if row:
                data = dict(row)
                # Parse tags JSON
                if data.get("tags"):
                    import json

                    try:
                        data["tags"] = json.loads(data["tags"])
                    except json.JSONDecodeError:
                        data["tags"] = []
                return data
            return None

    def get_paper_by_hash(self, file_hash: str) -> dict | None:
        """Get a paper by file hash."""
        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM papers WHERE file_hash = ?", (file_hash,)).fetchone()
            return dict(row) if row else None

    def list_papers(self, limit: int = 50) -> list[dict]:
        """List recent papers."""
        with self._get_connection() as conn:
            rows = conn.execute(
                """SELECT paper_id, filename, target_language, owner_id, visibility, created_at 
                   FROM papers ORDER BY created_at DESC LIMIT ?""",
                (limit,),
            ).fetchall()
            return [dict(row) for row in rows]

    def update_paper_html(self, paper_id: str, html_content: str) -> bool:
        """Update the HTML content of a paper."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE papers SET html_content = ?, updated_at = ? WHERE paper_id = ?",
                (html_content, now, paper_id),
            )
            conn.commit()
            conn.commit()
            return cursor.rowcount > 0

    def update_paper_abstract(self, paper_id: str, abstract: str) -> bool:
        """Update the abstract/summary of a paper."""
        now = datetime.now().isoformat()
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE papers SET abstract = ?, updated_at = ? WHERE paper_id = ?",
                (abstract, now, paper_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM papers WHERE paper_id = ?", (paper_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Paper deleted: {paper_id}")
            return deleted

    def update_paper_visibility(self, paper_id: str, visibility: str) -> bool:
        """Update paper visibility."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE papers SET visibility = ?, updated_at = ? WHERE paper_id = ?",
                (visibility, datetime.now().isoformat(), paper_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ===== Note methods =====

    def save_note(
        self,
        note_id: str,
        session_id: str,
        term: str,
        note: str,
        image_url: str | None = None,
        page_number: int | None = None,
        x: float | None = None,
        y: float | None = None,
        user_id: str | None = None,
    ) -> str:
        """Save a note."""
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO notes (note_id, session_id, term, note, image_url, page_number, x, y, user_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(note_id) DO UPDATE SET
                    term=excluded.term,
                    note=excluded.note,
                    image_url=excluded.image_url,
                    page_number=excluded.page_number,
                    x=excluded.x,
                    y=excluded.y,
                    user_id=excluded.user_id,
                    created_at=excluded.created_at
                """,
                (
                    note_id,
                    session_id,
                    term,
                    note,
                    image_url,
                    page_number,
                    x,
                    y,
                    user_id,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        logger.info(f"Note saved: {note_id} (user: {user_id})")
        return note_id

    def get_notes(self, session_id: str, user_id: str | None = None) -> list[dict]:
        """Get all notes for a session or user."""
        with self._get_connection() as conn:
            if user_id:
                # Get notes for user OR session (to keep guest notes if linked?)
                # For now let's just get user notes + session notes for that user context
                # Or just user notes if logged in.
                # Actually, if user is logged in, we probably only care about their notes,
                # but if they just logged in and had session notes, we might want both or merged.
                # Simplest: user_id takes precedence, but maybe include session_id too?
                # "session_id" is usually current browser session.
                # If we want to show all user's notes, we query by user_id.
                query = "SELECT * FROM notes WHERE user_id = ? OR session_id = ? ORDER BY created_at DESC"
                params = (user_id, session_id)
            else:
                query = "SELECT * FROM notes WHERE session_id = ? ORDER BY created_at DESC"
                params = (session_id,)

            rows = conn.execute(query, params).fetchall()
            return [dict(row) for row in rows]

    def delete_note(self, note_id: str) -> bool:
        """Delete a note by ID."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM notes WHERE note_id = ?", (note_id,))
            conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Note deleted: {note_id}")
            return deleted

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
        """Add a stamp to a paper."""
        import uuid6

        stamp_id = str(uuid6.uuid7())
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO paper_stamps (id, paper_id, user_id, stamp_type, page_number, x, y, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stamp_id,
                    paper_id,
                    user_id,
                    stamp_type,
                    page_number,
                    x,
                    y,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        logger.info(f"Paper stamp added: {stamp_id} to paper {paper_id}")
        return stamp_id

    def get_paper_stamps(self, paper_id: str) -> list[dict]:
        """Get stamps for a paper."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_stamps WHERE paper_id = ? ORDER BY created_at DESC",
                (paper_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_paper_stamp(self, stamp_id: str) -> bool:
        """Delete a stamp from a paper."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM paper_stamps WHERE id = ?", (stamp_id,))
            conn.commit()
            return cursor.rowcount > 0

    def add_note_stamp(
        self,
        note_id: str,
        stamp_type: str,
        user_id: str | None = None,
        x: float | None = None,
        y: float | None = None,
    ) -> str:
        """Add a stamp to a note."""
        import uuid6

        stamp_id = str(uuid6.uuid7())
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO note_stamps (id, note_id, user_id, stamp_type, x, y, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stamp_id,
                    note_id,
                    user_id,
                    stamp_type,
                    x,
                    y,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        logger.info(f"Note stamp added: {stamp_id} to note {note_id}")
        return stamp_id

    def get_note_stamps(self, note_id: str) -> list[dict]:
        """Get stamps for a note."""
        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM note_stamps WHERE note_id = ? ORDER BY created_at DESC",
                (note_id,),
            ).fetchall()
            return [dict(row) for row in rows]

    def delete_note_stamp(self, stamp_id: str) -> bool:
        """Delete a stamp from a note."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM note_stamps WHERE id = ?", (stamp_id,))
            conn.commit()
            return cursor.rowcount > 0

    # ===== Figure methods =====

    def save_figure(
        self,
        paper_id: str,
        page_number: int,
        bbox: list | tuple,
        image_url: str,
        caption: str = "",
        explanation: str = "",
    ) -> str:
        """Save a figure."""
        import json

        import uuid6

        figure_id = str(uuid6.uuid7())
        bbox_json = json.dumps(bbox)

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO paper_figures (id, paper_id, page_number, bbox_json, image_url, caption, explanation, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    figure_id,
                    paper_id,
                    page_number,
                    bbox_json,
                    image_url,
                    caption,
                    explanation,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
        return figure_id

    def get_paper_figures(self, paper_id: str) -> list[dict]:
        """Get figures for a paper."""
        import json

        with self._get_connection() as conn:
            rows = conn.execute(
                "SELECT * FROM paper_figures WHERE paper_id = ? ORDER BY page_number, created_at",
                (paper_id,),
            ).fetchall()
            results = []
            for row in rows:
                d = dict(row)
                if d.get("bbox_json"):
                    try:
                        d["bbox"] = json.loads(d["bbox_json"])
                    except Exception:
                        d["bbox"] = []
                results.append(d)
            return results

    def get_figure(self, figure_id: str) -> dict | None:
        """Get a figure by ID."""
        import json

        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM paper_figures WHERE id = ?", (figure_id,)).fetchone()
            if row:
                d = dict(row)
                if d.get("bbox_json"):
                    try:
                        d["bbox"] = json.loads(d["bbox_json"])
                    except Exception:
                        d["bbox"] = []
                return d
            return None

    def update_figure_explanation(self, figure_id: str, explanation: str) -> bool:
        """Update figure explanation."""
        with self._get_connection() as conn:
            cursor = conn.execute(
                "UPDATE paper_figures SET explanation = ? WHERE id = ?",
                (explanation, figure_id),
            )
            conn.commit()
            return cursor.rowcount > 0

    # ===== User methods =====

    def create_user(self, user_data: dict) -> str:
        """Create a new user."""
        import json

        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO users (id, email, display_name, affiliation, bio, 
                                   research_fields, profile_image_url, is_public, 
                                   created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    user_data.get("created_at", datetime.now()).isoformat(),
                    user_data.get("updated_at", datetime.now()).isoformat(),
                ),
            )
            conn.commit()
        logger.info(f"User created: {user_data['id']}")
        return user_data["id"]

    def get_user(self, user_id: str) -> dict | None:
        """Get a user by ID."""
        import json

        with self._get_connection() as conn:
            row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
            if row:
                data = dict(row)
                data["is_public"] = bool(data.get("is_public", 1))
                if data.get("research_fields"):
                    try:
                        data["research_fields"] = json.loads(data["research_fields"])
                    except json.JSONDecodeError:
                        data["research_fields"] = []
                else:
                    data["research_fields"] = []
                return data
            return None

    def update_user(self, user_id: str, data: dict) -> bool:
        """Update user data."""
        import json

        fields = []
        values = []
        for key, value in data.items():
            if key in ["id", "created_at"]:
                continue
            if key == "research_fields" and isinstance(value, list):
                value = json.dumps(value)
            if key == "is_public":
                value = 1 if value else 0
            fields.append(f"{key} = ?")
            values.append(value)

        if not fields:
            return False

        values.append(user_id)
        with self._get_connection() as conn:
            cursor = conn.execute(f"UPDATE users SET {', '.join(fields)} WHERE id = ?", values)
            conn.commit()
            return cursor.rowcount > 0

    def delete_user(self, user_id: str) -> bool:
        """Delete a user."""
        with self._get_connection() as conn:
            cursor = conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
            conn.commit()
            return cursor.rowcount > 0

    def get_user_stats(self, user_id: str) -> dict:
        """Get user statistics."""
        with self._get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM papers WHERE owner_id = ?", (user_id,)
            ).fetchone()[0]
            public = conn.execute(
                "SELECT COUNT(*) FROM papers WHERE owner_id = ? AND visibility = 'public'",
                (user_id,),
            ).fetchone()[0]
            views = conn.execute(
                "SELECT COALESCE(SUM(view_count), 0) FROM papers WHERE owner_id = ?",
                (user_id,),
            ).fetchone()[0]
            likes = conn.execute(
                "SELECT COALESCE(SUM(like_count), 0) FROM papers WHERE owner_id = ?",
                (user_id,),
            ).fetchone()[0]
            return {
                "paper_count": total,
                "public_paper_count": public,
                "total_views": views,
                "total_likes": likes,
            }

    def save_session_context(self, session_id: str, paper_id: str) -> None:
        """Save session to paper mapping."""
        try:
            with self._get_connection() as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO app_sessions (session_id, paper_id, created_at) VALUES (?, ?, ?)",
                    (session_id, paper_id, datetime.now().isoformat()),
                )
                conn.commit()
            logger.info(f"[Storage] Session context saved: {session_id} -> {paper_id}")
        except Exception as e:
            logger.error(f"[Storage] Failed to save session context: {e}")

    def get_session_paper_id(self, session_id: str) -> str | None:
        """Get paper ID for a session."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT paper_id FROM app_sessions WHERE session_id = ?", (session_id,)
            ).fetchone()
            return row[0] if row else None

    # ===== Social paper methods =====

    def get_user_papers(
        self, user_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        """Get all papers for a user."""
        offset = (page - 1) * per_page
        with self._get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM papers WHERE owner_id = ?", (user_id,)
            ).fetchone()[0]
            rows = conn.execute(
                """SELECT * FROM papers WHERE owner_id = ? 
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (user_id, per_page, offset),
            ).fetchall()
            return [dict(row) for row in rows], total

    def get_user_public_papers(
        self, user_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        """Get public papers for a user."""
        offset = (page - 1) * per_page
        with self._get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM papers WHERE owner_id = ? AND visibility = 'public'",
                (user_id,),
            ).fetchone()[0]
            rows = conn.execute(
                """SELECT * FROM papers WHERE owner_id = ? AND visibility = 'public'
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (user_id, per_page, offset),
            ).fetchall()
            return [dict(row) for row in rows], total

    def get_public_papers(
        self, page: int = 1, per_page: int = 20, sort: str = "recent"
    ) -> tuple[list[dict], int]:
        """Get all public papers for explore page."""
        offset = (page - 1) * per_page
        order_by = "created_at DESC"
        if sort == "popular":
            order_by = "view_count DESC"
        elif sort == "trending":
            order_by = "like_count DESC"

        with self._get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) FROM papers WHERE visibility = 'public'"
            ).fetchone()[0]
            rows = conn.execute(
                f"""SELECT * FROM papers WHERE visibility = 'public'
                   ORDER BY {order_by} LIMIT ? OFFSET ?""",
                (per_page, offset),
            ).fetchall()
            return [dict(row) for row in rows], total

    def search_public_papers(
        self, query: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        """Search public papers."""
        offset = (page - 1) * per_page
        search_pattern = f"%{query}%"
        with self._get_connection() as conn:
            total = conn.execute(
                """SELECT COUNT(*) FROM papers 
                   WHERE visibility = 'public' 
                   AND (title LIKE ? OR authors LIKE ? OR abstract LIKE ? OR filename LIKE ?)""",
                (search_pattern, search_pattern, search_pattern, search_pattern),
            ).fetchone()[0]
            rows = conn.execute(
                """SELECT * FROM papers 
                   WHERE visibility = 'public' 
                   AND (title LIKE ? OR authors LIKE ? OR abstract LIKE ? OR filename LIKE ?)
                   ORDER BY created_at DESC LIMIT ? OFFSET ?""",
                (search_pattern, search_pattern, search_pattern, search_pattern, per_page, offset),
            ).fetchall()
            return [dict(row) for row in rows], total

    def get_popular_tags(self, limit: int = 20) -> list[dict]:
        """Get popular tags."""
        # For now, return empty list - implement when tags are properly used
        return []

    def get_ocr_cache(self, file_hash: str) -> str | None:
        """Get cached OCR text."""
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT ocr_text FROM ocr_reader WHERE file_hash = ?", (file_hash,)
            ).fetchone()
            if row:
                return row[0]
            return None

    def save_ocr_cache(self, file_hash: str, ocr_text: str, filename: str, model_name: str) -> None:
        """Save OCR text to cache."""
        with self._get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO ocr_reader (file_hash, filename, ocr_text, model_name, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (file_hash, filename, ocr_text, model_name),
            )
            conn.commit()


# Singleton instance cache
_storage_provider_instance: StorageInterface | None = None


def get_storage_provider() -> StorageInterface:
    """
    Factory function to get the configured storage provider (singleton).

    Set STORAGE_PROVIDER environment variable:
    - "sqlite" (default): Use local SQLite
    - "cloudsql": Use Cloud SQL (requires GCP setup)
    """
    global _storage_provider_instance

    if _storage_provider_instance is not None:
        return _storage_provider_instance

    provider_type = os.getenv("STORAGE_PROVIDER", "sqlite").lower()

    if provider_type == "cloudsql":
        try:
            from .cloud_sql_storage import CloudSQLStorage

            _storage_provider_instance = CloudSQLStorage()
        except ImportError as e:
            logger.error(f"Failed to import CloudSQLStorage: {e}")
            raise RuntimeError(
                "CloudSQLStorage requires 'psycopg2' and 'cloud_sql_storage.py'"
            ) from e
    else:
        _storage_provider_instance = SQLiteStorage()

    return _storage_provider_instance
