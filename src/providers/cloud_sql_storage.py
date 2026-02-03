"""
Cloud SQL Storage Provider
"""

import json
import os
from datetime import datetime

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

    def init_tables(self) -> None:
        """Legacy method retained for interface compatibility (now handled by Alembic)."""
        pass

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
        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO papers 
                    (paper_id, file_hash, filename, ocr_text, html_content, target_language, 
                     layout_json, owner_id, visibility, title, created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (paper_id) DO UPDATE SET
                    file_hash = EXCLUDED.file_hash,
                    filename = EXCLUDED.filename,
                    ocr_text = EXCLUDED.ocr_text,
                    html_content = EXCLUDED.html_content,
                    target_language = EXCLUDED.target_language,
                    layout_json = EXCLUDED.layout_json,
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
                        layout_json,
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
                    """SELECT paper_id, filename, title, target_language, owner_id, visibility, created_at 
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
                conn.commit()
                return cur.rowcount > 0

    def update_paper_abstract(self, paper_id: str, abstract: str) -> bool:
        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE papers SET abstract = %s, updated_at = %s WHERE paper_id = %s",
                    (abstract, now, paper_id),
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
        page_number: int | None = None,
        x: float | None = None,
        y: float | None = None,
        user_id: str | None = None,
        paper_id: str | None = None,
    ) -> str:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO notes (note_id, session_id, term, note, image_url, page_number, x, y, user_id, paper_id, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (note_id) DO UPDATE SET
                        term = EXCLUDED.term,
                        note = EXCLUDED.note,
                        image_url = EXCLUDED.image_url,
                        page_number = EXCLUDED.page_number,
                        x = EXCLUDED.x,
                        y = EXCLUDED.y,
                        user_id = EXCLUDED.user_id,
                        paper_id = EXCLUDED.paper_id,
                        created_at = EXCLUDED.created_at
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
                        paper_id,
                        datetime.now(),
                    ),
                )
            conn.commit()
        return note_id

    def get_notes(
        self, session_id: str, paper_id: str | None = None, user_id: str | None = None
    ) -> list[dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                query = "SELECT * FROM notes WHERE "
                conditions = []
                params = []

                if paper_id:
                    conditions.append("paper_id = %s")
                    params.append(paper_id)

                if user_id:
                    conditions.append("(user_id = %s OR (user_id IS NULL AND session_id = %s))")
                    params.extend([user_id, session_id])
                else:
                    conditions.append("session_id = %s")
                    params.append(session_id)

                query += " AND ".join(conditions) + " ORDER BY created_at DESC"
                cur.execute(query, tuple(params))
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

    # ===== Figure methods =====

    def save_figure(
        self,
        paper_id: str,
        page_number: int,
        bbox: list | tuple,
        image_url: str,
        caption: str = "",
        explanation: str = "",
        label: str = "figure",
        latex: str = "",
    ) -> str:
        import uuid6

        figure_id = str(uuid6.uuid7())
        import json

        bbox_json = json.dumps(bbox)

        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO paper_figures (id, paper_id, page_number, bbox_json, image_url, caption, explanation, label, latex, created_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        figure_id,
                        paper_id,
                        page_number,
                        bbox_json,
                        image_url,
                        caption,
                        explanation,
                        label,
                        latex,
                        datetime.now(),
                    ),
                )
            conn.commit()
        return figure_id

    def get_paper_figures(self, paper_id: str) -> list[dict]:
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT * FROM paper_figures WHERE paper_id = %s ORDER BY page_number, created_at",
                    (paper_id,),
                )
                rows = cur.fetchall()
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
        with self._get_connection() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("SELECT * FROM paper_figures WHERE id = %s", (figure_id,))
                row = cur.fetchone()
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
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE paper_figures SET explanation = %s WHERE id = %s",
                    (explanation, figure_id),
                )
            conn.commit()
            return cur.rowcount > 0

    def update_figure_latex(self, figure_id: str, latex: str) -> bool:
        """Update figure LaTeX."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE paper_figures SET latex = %s WHERE id = %s",
                    (latex, figure_id),
                )
            conn.commit()
            return cur.rowcount > 0

    def update_paper_full_summary(self, paper_id: str, summary: str) -> bool:
        """Update the full summary of a paper."""
        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE papers SET full_summary = %s, updated_at = %s WHERE paper_id = %s",
                    (summary, now, paper_id),
                )
            conn.commit()
            return cur.rowcount > 0

    def update_paper_section_summary(self, paper_id: str, json_summary: str) -> bool:
        """Update the section summary (JSON) of a paper."""
        now = datetime.now()
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE papers SET section_summary_json = %s, updated_at = %s WHERE paper_id = %s",
                    (json_summary, now, paper_id),
                )
            conn.commit()
            return cur.rowcount > 0

    # ===== User methods =====

    def create_user(self, user_data: dict) -> str:
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, email, display_name, affiliation, bio, 
                                       research_fields, profile_image_url, is_public, plan,
                                       created_at, updated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                        user_data.get("plan", "free"),
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
                    data["plan"] = data.get("plan", "free")
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

    def save_session_context(self, session_id: str, paper_id: str) -> None:
        """Save session to paper mapping."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO app_sessions (session_id, paper_id, created_at) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (session_id) DO UPDATE SET
                    paper_id = EXCLUDED.paper_id,
                    created_at = EXCLUDED.created_at
                    """,
                    (session_id, paper_id, datetime.now()),
                )
            conn.commit()

    def get_session_paper_id(self, session_id: str) -> str | None:
        """Get paper ID for a session."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT paper_id FROM app_sessions WHERE session_id = %s", (session_id,)
                )
                row = cur.fetchone()
                return row[0] if row else None

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

    def get_ocr_cache(self, file_hash: str) -> dict | None:
        """Get cached OCR text and layout."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT ocr_text, layout_json FROM ocr_reader WHERE file_hash = %s",
                    (file_hash,),
                )
                row = cur.fetchone()
                if row:
                    return {"ocr_text": row[0], "layout_json": row[1]}
                return None

    def save_ocr_cache(
        self,
        file_hash: str,
        ocr_text: str,
        filename: str,
        model_name: str,
        layout_json: str | None = None,
    ) -> None:
        """Save OCR text to cache."""
        with self._get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO ocr_reader (file_hash, filename, ocr_text, layout_json, model_name)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (file_hash) DO UPDATE SET
                       filename = EXCLUDED.filename,
                       ocr_text = EXCLUDED.ocr_text,
                       layout_json = EXCLUDED.layout_json,
                       model_name = EXCLUDED.model_name,
                       created_at = CURRENT_TIMESTAMP""",
                    (file_hash, filename, ocr_text, layout_json, model_name),
                )
            conn.commit()
