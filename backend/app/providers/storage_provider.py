"""
Storage Provider abstraction layer.
"""

from abc import ABC, abstractmethod
from contextvars import ContextVar
from typing import Any, Optional

from common.config import settings  # noqa: F401
from common.logger import ServiceLogger

log = ServiceLogger("Storage")


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
        layout_json: Optional[str] = None,
        owner_id: Optional[str] = None,
        visibility: str = "private",
    ) -> str:
        """Save a paper to storage. Returns paper_id."""
        ...

    @abstractmethod
    def get_paper(self, paper_id: str) -> Optional[dict]:
        """Get a paper by ID."""
        ...

    @abstractmethod
    def get_paper_by_hash(self, file_hash: str) -> Optional[dict]:
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
        """Update the abstract of a paper."""
        ...

    @abstractmethod
    def update_paper_title(self, paper_id: str, title: str) -> bool:
        """Update the title of a paper."""
        ...

    @abstractmethod
    def update_paper_authors(self, paper_id: str, authors: str) -> bool:
        """Update the authors of a paper."""
        ...

    @abstractmethod
    def update_paper_ocr_text(self, paper_id: str, ocr_text: str) -> bool:
        """Update the OCR text of a paper (used for GROBID structured text replacement)."""
        ...

    @abstractmethod
    def update_paper_full_summary(self, paper_id: str, summary: str) -> bool:
        """Update the full summary of a paper."""
        ...

    @abstractmethod
    def update_paper_section_summary(self, paper_id: str, json_summary: str) -> bool:
        """Update the section summary of a paper."""
        ...

    @abstractmethod
    def delete_paper(self, paper_id: str) -> bool:
        """Delete a paper from storage."""
        ...

    @abstractmethod
    def update_paper_layout(self, paper_id: str, layout_json: str) -> bool:
        """Update the layout JSON of a paper."""
        ...

    @abstractmethod
    def update_paper_visibility(self, paper_id: str, visibility: str) -> bool:
        """Update the visibility of a paper."""
        ...

    @abstractmethod
    def increment_like_count(self, paper_id: str) -> bool:
        """Increment the like count of a paper."""
        ...

    @abstractmethod
    def decrement_like_count(self, paper_id: str) -> bool:
        """Decrement the like count of a paper."""
        ...

    # ===== Note methods =====

    @abstractmethod
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
        """Save a note to storage. Returns note_id."""
        ...

    @abstractmethod
    def get_notes(
        self,
        session_id: str,
        paper_id: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> list[dict]:
        """Get notes by session ID or paper ID."""
        ...

    @abstractmethod
    def delete_note(self, note_id: str) -> bool:
        """Delete a note from storage."""
        ...

    # ===== Stamp methods =====

    @abstractmethod
    def add_paper_stamp(
        self,
        paper_id: str,
        stamp_type: str,
        user_id: Optional[str] = None,
        page_number: Optional[int] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
    ) -> str:
        """Add a stamp to a paper."""
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
        user_id: Optional[str] = None,
        x: Optional[float] = None,
        y: Optional[float] = None,
    ) -> str:
        """Add a stamp to a note."""
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
        label: str = "figure",
        latex: str = "",
    ) -> str:
        """Save a figure information to storage."""
        ...

    @abstractmethod
    def save_figures_batch(self, paper_id: str, figures: list[dict]) -> list[str]:
        """Save a batch of figures to storage."""
        ...

    @abstractmethod
    def get_paper_figures(self, paper_id: str) -> list[dict]:
        """Get all figures of a paper."""
        ...

    @abstractmethod
    def get_figure(self, figure_id: str) -> Optional[dict]:
        """Get a single figure information."""
        ...

    @abstractmethod
    def update_figure_explanation(self, figure_id: str, explanation: str) -> bool:
        """Update figure explanation."""
        ...

    @abstractmethod
    def update_figure_latex(self, figure_id: str, latex: str) -> bool:
        """Update figure latex command."""
        ...

    # ===== User methods =====

    @abstractmethod
    def create_user(self, user_data: dict) -> str:
        """Create a new user."""
        ...

    @abstractmethod
    def get_user(self, user_id: str) -> Optional[dict]:
        """Get user info by user ID."""
        ...

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[dict]:
        """Get user info by email."""
        ...

    @abstractmethod
    def update_user(self, user_id: str, data: dict) -> bool:
        """Update user information."""
        ...

    @abstractmethod
    def migrate_user_uid(self, old_uid: str, new_uid: str) -> bool:
        """Migrate user UID from old to new."""
        ...

    @abstractmethod
    def delete_user(self, user_id: str) -> bool:
        """Delete user account."""
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
        """Get papers owned by a user (paginated)."""
        ...

    @abstractmethod
    def get_user_public_papers(
        self, user_id: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        """Get public papers owned by a user."""
        ...

    @abstractmethod
    def get_public_papers(
        self, page: int = 1, per_page: int = 20, sort: str = "recent"
    ) -> tuple[list[dict], int]:
        """Get all public papers (paginated)."""
        ...

    @abstractmethod
    def search_public_papers(
        self, query: str, page: int = 1, per_page: int = 20
    ) -> tuple[list[dict], int]:
        """Search public papers by query."""
        ...

    @abstractmethod
    def get_popular_tags(self, limit: int = 20) -> list[dict]:
        """Get popular tags."""
        ...

    # ===== OCR cache methods =====

    @abstractmethod
    def get_ocr_cache(self, file_hash: str) -> Optional[dict]:
        """Get OCR cache by file hash."""
        ...

    @abstractmethod
    def save_ocr_cache(
        self,
        file_hash: str,
        ocr_text: str,
        filename: str,
        model_name: str,
        layout_json: Optional[str] = None,
    ) -> None:
        """Save OCR result to cache."""
        ...

    # ===== Session methods (Redis/Storage generic) =====

    @abstractmethod
    def save_session_context(self, session_id: str, paper_id: str) -> None:
        """Save session context (e.g. current paper ID)."""
        ...

    @abstractmethod
    def get_session_paper_id(self, session_id: str) -> Optional[str]:
        """Get current paper ID by session ID."""
        ...

    # ===== Chat history methods =====

    @abstractmethod
    def save_chat_history(self, user_id: str, paper_id: str, messages: list) -> None:
        """Save chat history."""
        ...

    @abstractmethod
    def get_chat_history(self, user_id: str, paper_id: str) -> list:
        """Get chat history by user and paper."""
        ...

    @abstractmethod
    def close(self) -> None:
        """Close connection or session."""
        ...

    @abstractmethod
    def clear_all_data(self) -> bool:
        """Clear all data from storage."""
        ...


# Request-scoped storage context
storage_context: ContextVar[Optional[Any]] = ContextVar("storage_context", default=None)


def get_storage_provider() -> StorageInterface:
    """
    Returns the storage provider (ORMStorageAdapter).
    Uses request-scoped context if available to prevent session leaks.
    """
    # Try to get existing request-scoped storage
    storage = storage_context.get()
    if storage is not None:
        return storage

    # Fallback for background tasks or non-request contexts
    from app.database import SessionLocal
    from app.providers.orm_storage import ORMStorageAdapter

    db = SessionLocal()
    return ORMStorageAdapter(db)
