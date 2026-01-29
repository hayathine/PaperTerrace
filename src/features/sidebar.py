"""
sidebarに用語やノートを表示・保存する機能を提供するモジュール
"""

import uuid6

from src.logger import logger
from src.providers import get_storage_provider


class NoteError(Exception):
    """Note-specific exception."""

    pass


class SidebarNoteService:
    """Sidebar note service for storing notes and terms."""

    def __init__(self):
        self.storage = get_storage_provider()

    def add_note(
        self,
        session_id: str,
        term: str,
        note: str,
        image_url: str | None = None,
        page_number: int | None = None,
        x: float | None = None,
        y: float | None = None,
        user_id: str | None = None,
    ) -> dict:
        """
        Add a note to the sidebar.

        Args:
            session_id: The session identifier
            term: The term or keyword
            note: The note content
            image_url: Optional image URL
            page_number: Page number for jump
            x: X coordinate (relative %)
            y: Y coordinate (relative %)
            user_id: Optional user identifier (if logged in)

        Returns:
            The created note with its ID
        """
        try:
            note_id = str(uuid6.uuid7())
            self.storage.save_note(
                note_id, session_id, term, note, image_url, page_number, x, y, user_id
            )
            logger.info(
                "Note added",
                extra={
                    "note_id": note_id,
                    "session_id": session_id,
                    "term": term,
                    "user_id": user_id,
                    "page": page_number,
                },
            )
            return {
                "note_id": note_id,
                "session_id": session_id,
                "term": term,
                "note": note,
                "image_url": image_url,
                "page_number": page_number,
                "x": x,
                "y": y,
                "user_id": user_id,
            }
        except Exception as e:
            logger.exception(
                "Failed to add note",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise NoteError(f"ノートの保存に失敗しました: {e}") from e

    def get_notes(self, session_id: str, user_id: str | None = None) -> list[dict]:
        """
        Get all notes for a session or user.

        Args:
            session_id: The session identifier
            user_id: Optional user identifier

        Returns:
            List of notes
        """
        try:
            notes = self.storage.get_notes(session_id, user_id)
            logger.info(
                "Notes retrieved",
                extra={"session_id": session_id, "user_id": user_id, "count": len(notes)},
            )

            return notes
        except Exception as e:
            logger.exception(
                "Failed to retrieve notes",
                extra={"session_id": session_id, "error": str(e)},
            )
            return []

    def delete_note(self, note_id: str) -> bool:
        """
        Delete a note.

        Args:
            note_id: The note identifier

        Returns:
            True if deleted, False otherwise
        """
        try:
            deleted = self.storage.delete_note(note_id)
            if deleted:
                logger.info(
                    "Note deleted",
                    extra={"note_id": note_id},
                )
            else:
                logger.warning(
                    "Note not found for deletion",
                    extra={"note_id": note_id},
                )
            return deleted
        except Exception as e:
            logger.exception(
                "Failed to delete note",
                extra={"note_id": note_id, "error": str(e)},
            )
            return False

    def clear_session_notes(self, session_id: str) -> int:
        """
        Clear all notes for a session.

        Args:
            session_id: The session identifier

        Returns:
            Number of notes deleted
        """
        notes = self.get_notes(session_id)
        count = 0
        for note in notes:
            if self.delete_note(note["note_id"]):
                count += 1
        logger.info(f"Cleared {count} notes for session {session_id}")
        return count

    def export_notes(self, session_id: str) -> str:
        """
        Export notes as formatted text.

        Args:
            session_id: The session identifier

        Returns:
            Formatted note text
        """
        notes = self.get_notes(session_id)
        if not notes:
            return "ノートがありません。"

        lines = ["# 保存したノート\n"]
        for note in notes:
            lines.append(f"## {note['term']}")
            lines.append(f"{note['note']}\n")
            lines.append(f"_保存日時: {note.get('created_at', 'N/A')}_\n")
            lines.append("---\n")

        return "\n".join(lines)
