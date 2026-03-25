"""
ORMStorageAdapter: StorageInterface を SQLAlchemy ORM リポジトリで実装するアダプター。

生 SQL を使った PostgreSQLStorage / CloudSQLStorage の代替として、
ORM モデルを単一の変更箇所として扱えるようにする。
"""

import json
from typing import Optional

from sqlalchemy.exc import InvalidRequestError, OperationalError, PendingRollbackError
from sqlalchemy.orm import Session

from app.models.orm.figure import PaperFigure
from app.models.orm.note import Note
from app.models.orm.paper import Paper
from app.models.orm.stamp import NoteStamp, PaperStamp
from app.models.orm.user import User
from app.models.repositories.chat_history_repository import ChatHistoryRepository
from app.models.repositories.figure_repository import FigureRepository
from app.models.repositories.note_repository import NoteRepository
from app.models.repositories.ocr_repository import OCRRepository
from app.models.repositories.paper_repository import PaperRepository
from app.models.repositories.stamp_repository import StampRepository
from app.models.repositories.user_repository import UserRepository
from app.providers.storage_provider import StorageInterface


def _paper_to_dict(paper: Paper) -> dict:
    """Paper ORM インスタンスを dict に変換する。"""
    d = {c.name: getattr(paper, c.name) for c in paper.__table__.columns}
    # tags は JSON 文字列 → list に変換
    if d.get("tags"):
        try:
            d["tags"] = json.loads(d["tags"])
        except (json.JSONDecodeError, TypeError):
            d["tags"] = []
    else:
        d["tags"] = []
    return d


def _user_to_dict(user: User) -> dict:
    """User ORM インスタンスを dict に変換する。"""
    d = {c.name: getattr(user, c.name) for c in user.__table__.columns}
    d["is_public"] = bool(d.get("is_public", 1))
    if d.get("research_fields"):
        try:
            if isinstance(d["research_fields"], str):
                d["research_fields"] = json.loads(d["research_fields"])
        except (json.JSONDecodeError, TypeError):
            d["research_fields"] = []
    else:
        d["research_fields"] = []
    return d


def _figure_to_dict(fig: PaperFigure) -> dict:
    """PaperFigure ORM インスタンスを dict に変換する。"""
    d = {c.name: getattr(fig, c.name) for c in fig.__table__.columns}
    d["figure_id"] = d["id"]
    d["page_num"] = d.get("page_number")
    if d.get("bbox_json"):
        try:
            d["bbox"] = json.loads(d["bbox_json"])
        except (json.JSONDecodeError, TypeError):
            d["bbox"] = []
    else:
        d["bbox"] = []
    return d


def _note_to_dict(note: Note) -> dict:
    """Note ORM インスタンスを dict に変換する。"""
    return {c.name: getattr(note, c.name) for c in note.__table__.columns}


def _stamp_to_dict(stamp) -> dict:
    """Stamp ORM インスタンスを dict に変換する。"""
    return {c.name: getattr(stamp, c.name) for c in stamp.__table__.columns}


class ORMStorageAdapter(StorageInterface):
    """
    StorageInterface を SQLAlchemy ORM リポジトリで実装するアダプター。

    全ての DB アクセスをリポジトリ経由に統一することで、
    テーブル定義の変更を ORM モデル 1 箇所の修正に抑える。

    セッション自己回復 (catch-and-retry):
    シングルトンとして長期利用される場合、DB エラーによってセッションが
    PendingRollback 状態になることがある。_with_recovery() が PendingRollbackError /
    InvalidRequestError を捕捉するとセッションを置き換えて一度だけリトライする。
    """

    def __init__(self, db: Session):
        self._db = db
        self._init_repositories(db)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_repositories(self, db: Session) -> None:
        """リポジトリをセッションで初期化する。"""
        self.db = db
        self.papers = PaperRepository(db)
        self.notes = NoteRepository(db)
        self.figures = FigureRepository(db)
        self.stamps = StampRepository(db)
        self.users = UserRepository(db)
        self.ocr = OCRRepository(db)
        self.chat = ChatHistoryRepository(db)

    def _replace_session(self) -> None:
        """現在のセッションをクローズし、新しいセッションで全リポジトリを再初期化する。"""
        from app.database import SessionLocal

        try:
            self._db.rollback()
            self._db.close()
        except Exception:
            pass

        new_db = SessionLocal()
        self._db = new_db
        self._init_repositories(new_db)

    def _with_recovery(self, fn):
        """
        fn() を実行し、PendingRollbackError / InvalidRequestError が発生した場合は
        セッションを置き換えて 1 回だけリトライする。

        使い方:
            return self._with_recovery(lambda: self.papers.list_by_owner(uid))
        """
        try:
            return fn()
        except (PendingRollbackError, InvalidRequestError, OperationalError):
            self._replace_session()
            return fn()

    def close(self) -> None:
        """DBセッションをクローズしてプールに接続を返却する。"""
        try:
            self._db.close()
        except Exception:
            pass

    # ------------------------------------------------------------------

    def init_tables(self) -> None:
        """Alembic によるマイグレーションに委譲するため何もしない。"""
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
        layout_json: Optional[str] = None,
        owner_id: Optional[str] = None,
        visibility: str = "private",
    ) -> str:
        return self._with_recovery(
            lambda: self.papers.upsert(
                paper_id=paper_id,
                file_hash=file_hash,
                filename=filename,
                ocr_text=ocr_text,
                html_content=html_content,
                target_language=target_language,
                layout_json=layout_json,
                owner_id=owner_id,
                visibility=visibility,
            )
        )

    def get_paper(self, paper_id: str) -> Optional[dict]:
        paper = self._with_recovery(lambda: self.papers.get_by_id(paper_id))
        return _paper_to_dict(paper) if paper else None

    def get_paper_by_hash(self, file_hash: str) -> Optional[dict]:
        paper = self._with_recovery(lambda: self.papers.get_by_hash(file_hash))
        return _paper_to_dict(paper) if paper else None

    def list_papers(self, limit: int = 50) -> list[dict]:
        return [
            _paper_to_dict(p)
            for p in self._with_recovery(lambda: self.papers.list_recent(limit))
        ]

    def update_paper_html(self, paper_id: str, html_content: str) -> bool:
        return self._with_recovery(
            lambda: self.papers.update_html(paper_id, html_content)
        )

    def update_paper_abstract(self, paper_id: str, abstract: str) -> bool:
        return self._with_recovery(
            lambda: self.papers.update_abstract(paper_id, abstract)
        )

    def update_paper_full_summary(self, paper_id: str, summary: str) -> bool:
        return self._with_recovery(
            lambda: self.papers.update_full_summary(paper_id, summary)
        )

    def update_paper_section_summary(self, paper_id: str, json_summary: str) -> bool:
        return self._with_recovery(
            lambda: self.papers.update_section_summary(paper_id, json_summary)
        )

    def delete_paper(self, paper_id: str) -> bool:
        return self._with_recovery(lambda: self.papers.delete(paper_id))

    def update_paper_layout(self, paper_id: str, layout_json: str) -> bool:
        return self._with_recovery(
            lambda: self.papers.update_layout(paper_id, layout_json)
        )

    def update_paper_visibility(self, paper_id: str, visibility: str) -> bool:
        return self._with_recovery(
            lambda: self.papers.update_visibility(paper_id, visibility)
        )

    def increment_like_count(self, paper_id: str) -> bool:
        return self._with_recovery(lambda: self.papers.increment_like_count(paper_id))

    def decrement_like_count(self, paper_id: str) -> bool:
        return self._with_recovery(lambda: self.papers.decrement_like_count(paper_id))

    # ===== Note methods =====

    def save_note(
        self,
        note_id: str,
        session_id: str,
        term: str,
        note: str,
        image_url: Optional[str] = None,
        page_number: Optional[int] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
        user_id: Optional[str] = None,
        paper_id: Optional[str] = None,
    ) -> str:
        return self._with_recovery(
            lambda: self.notes.upsert(
                note_id=note_id,
                session_id=session_id,
                term=term,
                note=note,
                image_url=image_url,
                page_number=page_number,
                x=x,
                y=y,
                user_id=user_id,
                paper_id=paper_id,
            )
        )

    def get_notes(
        self,
        session_id: str,
        paper_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        rows = self._with_recovery(
            lambda: self.notes.get_for_session(
                session_id, paper_id=paper_id, user_id=user_id
            )
        )
        return [_note_to_dict(n) for n in rows]

    def delete_note(self, note_id: str) -> bool:
        return self._with_recovery(lambda: self.notes.delete(note_id))

    # ===== Stamp methods =====

    def add_paper_stamp(
        self,
        paper_id: str,
        stamp_type: str,
        user_id: Optional[str] = None,
        page_number: Optional[int] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
    ) -> str:
        return self._with_recovery(
            lambda: self.stamps.add_paper_stamp(
                paper_id=paper_id,
                stamp_type=stamp_type,
                user_id=user_id,
                page_number=page_number,
                x=x,
                y=y,
            )
        )

    def get_paper_stamps(self, paper_id: str) -> list[dict]:
        return [
            _stamp_to_dict(s)
            for s in self._with_recovery(lambda: self.stamps.get_paper_stamps(paper_id))
        ]

    def delete_paper_stamp(self, stamp_id: str) -> bool:
        return self._with_recovery(lambda: self.stamps.delete_paper_stamp(stamp_id))

    def add_note_stamp(
        self,
        note_id: str,
        stamp_type: str,
        user_id: Optional[str] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
    ) -> str:
        return self._with_recovery(
            lambda: self.stamps.add_note_stamp(
                note_id=note_id,
                stamp_type=stamp_type,
                user_id=user_id,
                x=x,
                y=y,
            )
        )

    def get_note_stamps(self, note_id: str) -> list[dict]:
        return [
            _stamp_to_dict(s)
            for s in self._with_recovery(lambda: self.stamps.get_note_stamps(note_id))
        ]

    def delete_note_stamp(self, stamp_id: str) -> bool:
        return self._with_recovery(lambda: self.stamps.delete_note_stamp(stamp_id))

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
        ids = self.save_figures_batch(
            paper_id,
            [
                {
                    "page_number": page_number,
                    "bbox": bbox,
                    "image_url": image_url,
                    "caption": caption,
                    "explanation": explanation,
                    "label": label,
                    "latex": latex,
                }
            ],
        )
        return ids[0]

    def save_figures_batch(self, paper_id: str, figures: list[dict]) -> list[str]:
        return self._with_recovery(lambda: self.figures.save_batch(paper_id, figures))

    def get_paper_figures(self, paper_id: str) -> list[dict]:
        return [
            _figure_to_dict(f)
            for f in self._with_recovery(lambda: self.figures.get_by_paper(paper_id))
        ]

    def get_figure(self, figure_id: str) -> Optional[dict]:
        fig = self._with_recovery(lambda: self.figures.get_by_id(figure_id))
        return _figure_to_dict(fig) if fig else None

    def update_figure_explanation(self, figure_id: str, explanation: str) -> bool:
        return self._with_recovery(
            lambda: self.figures.update_explanation(figure_id, explanation)
        )

    def update_figure_latex(self, figure_id: str, latex: str) -> bool:
        return self._with_recovery(lambda: self.figures.update_latex(figure_id, latex))

    # ===== User methods =====

    def create_user(self, user_data: dict) -> str:
        return self._with_recovery(lambda: self.users.create(user_data))

    def get_user(self, user_id: str) -> Optional[dict]:
        user = self._with_recovery(lambda: self.users.get_by_id(user_id))
        return _user_to_dict(user) if user else None

    def get_user_by_email(self, email: str) -> Optional[dict]:
        user = self._with_recovery(lambda: self.users.get_by_email(email))
        return _user_to_dict(user) if user else None

    def update_user(self, user_id: str, data: dict) -> bool:
        return self._with_recovery(lambda: self.users.update(user_id, data))

    def migrate_user_uid(self, old_uid: str, new_uid: str) -> bool:
        return self._with_recovery(lambda: self.users.migrate_uid(old_uid, new_uid))

    def delete_user(self, user_id: str) -> bool:
        return self._with_recovery(lambda: self.users.delete(user_id))

    def get_user_stats(self, user_id: str) -> dict:
        return self._with_recovery(lambda: self.papers.get_user_stats(user_id))

    # ===== Social paper methods =====

    def get_user_papers(
        self, user_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        rows, total = self._with_recovery(
            lambda: self.papers.list_by_owner(user_id, page, per_page)
        )
        return [_paper_to_dict(p) for p in rows], total

    def get_user_public_papers(
        self, user_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        rows, total = self._with_recovery(
            lambda: self.papers.list_public_by_owner(user_id, page, per_page)
        )
        return [_paper_to_dict(p) for p in rows], total

    def get_public_papers(
        self, page: int = 1, per_page: int = 20, sort: str = "recent"
    ) -> tuple[list[dict], int]:
        rows, total = self._with_recovery(
            lambda: self.papers.list_public(page, per_page, sort)
        )
        return [_paper_to_dict(p) for p in rows], total

    def search_public_papers(
        self, query: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        rows, total = self._with_recovery(
            lambda: self.papers.search_public(query, page, per_page)
        )
        return [_paper_to_dict(p) for p in rows], total

    def get_popular_tags(self, limit: int = 20) -> list[dict]:
        return self._with_recovery(lambda: self.papers.get_popular_tags(limit))

    # ===== OCR cache methods =====

    def get_ocr_cache(self, file_hash: str) -> Optional[dict]:
        return self._with_recovery(lambda: self.ocr.get_cache(file_hash))

    def save_ocr_cache(
        self,
        file_hash: str,
        ocr_text: str,
        filename: str,
        model_name: str,
        layout_json: Optional[str] = None,
    ) -> None:
        self._with_recovery(
            lambda: self.ocr.save_cache(
                file_hash, ocr_text, filename, model_name, layout_json
            )
        )

    # ===== Session methods (Redis) =====

    _SESSION_PAPER_TTL = 86400  # 24時間

    def save_session_context(self, session_id: str, paper_id: str) -> None:
        """セッション→論文マッピングをRedisに保存する。"""
        from redis_provider.provider import RedisService
        RedisService().set(f"session_pid:{session_id}", paper_id, expire=self._SESSION_PAPER_TTL)

    def get_session_paper_id(self, session_id: str) -> Optional[str]:
        """RedisからセッションIDに対応する論文IDを取得する。"""
        from redis_provider.provider import RedisService
        val = RedisService().get(f"session_pid:{session_id}")
        return str(val) if val is not None else None

    # ===== Chat history methods =====

    def save_chat_history(self, user_id: str, paper_id: str, messages: list) -> None:
        """チャット履歴を保存する。"""
        self._with_recovery(lambda: self.chat.save(user_id, paper_id, messages))

    def get_chat_history(self, user_id: str, paper_id: str) -> list:
        """チャット履歴を取得する。"""
        return self._with_recovery(lambda: self.chat.get(user_id, paper_id))

    # ===== Misc =====

    def clear_all_data(self) -> bool:
        """全データを削除する（主にテスト用途）。"""
        from app.models.orm.figure import PaperFigure
        from app.models.orm.note import Note
        from app.models.orm.ocr import OCRCache
        from app.models.orm.paper import Paper

        def _do_clear():
            for model in [
                NoteStamp,
                PaperStamp,
                PaperFigure,
                Note,
                OCRCache,
                Paper,
            ]:
                self.db.query(model).delete()
            self.db.commit()
            return True

        return self._with_recovery(_do_clear)
