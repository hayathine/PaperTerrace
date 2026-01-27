"""
sidebarに用語やメモを表示・保存する機能を提供するモジュール
"""

import uuid6

from src.logger import logger
from src.providers import get_storage_provider


class MemoError(Exception):
    """Memo-specific exception."""

    pass


class SidebarMemoService:
    """Sidebar memo service for storing notes and terms."""

    def __init__(self):
        self.storage = get_storage_provider()

    def add_memo(self, session_id: str, term: str, note: str) -> dict:
        """
        Add a memo to the sidebar.

        Args:
            session_id: The session identifier
            term: The term or keyword
            note: The note content

        Returns:
            The created memo with its ID
        """
        try:
            memo_id = str(uuid6.uuid7())
            self.storage.save_memo(memo_id, session_id, term, note)
            logger.info(
                "Memo added",
                extra={
                    "memo_id": memo_id,
                    "session_id": session_id,
                    "term": term,
                },
            )
            return {
                "memo_id": memo_id,
                "session_id": session_id,
                "term": term,
                "note": note,
            }
        except Exception as e:
            logger.exception(
                "Failed to add memo",
                extra={"session_id": session_id, "error": str(e)},
            )
            raise MemoError(f"メモの保存に失敗しました: {e}") from e

    def get_memos(self, session_id: str) -> list[dict]:
        """
        Get all memos for a session.

        Args:
            session_id: The session identifier

        Returns:
            List of memos
        """
        try:
            memos = self.storage.get_memos(session_id)
            logger.info(
                "Memos retrieved",
                extra={"session_id": session_id, "count": len(memos)},
            )

            return memos
        except Exception as e:
            logger.exception(
                "Failed to retrieve memos",
                extra={"session_id": session_id, "error": str(e)},
            )
            return []

    def delete_memo(self, memo_id: str) -> bool:
        """
        Delete a memo.

        Args:
            memo_id: The memo identifier

        Returns:
            True if deleted, False otherwise
        """
        try:
            deleted = self.storage.delete_memo(memo_id)
            if deleted:
                logger.info(
                    "Memo deleted",
                    extra={"memo_id": memo_id},
                )
            else:
                logger.warning(
                    "Memo not found for deletion",
                    extra={"memo_id": memo_id},
                )
            return deleted
        except Exception as e:
            logger.exception(
                "Failed to delete memo",
                extra={"memo_id": memo_id, "error": str(e)},
            )
            return False

    def clear_session_memos(self, session_id: str) -> int:
        """
        Clear all memos for a session.

        Args:
            session_id: The session identifier

        Returns:
            Number of memos deleted
        """
        memos = self.get_memos(session_id)
        count = 0
        for memo in memos:
            if self.delete_memo(memo["memo_id"]):
                count += 1
        logger.info(f"Cleared {count} memos for session {session_id}")
        return count

    def export_memos(self, session_id: str) -> str:
        """
        Export memos as formatted text.

        Args:
            session_id: The session identifier

        Returns:
            Formatted memo text
        """
        memos = self.get_memos(session_id)
        if not memos:
            return "メモがありません。"

        lines = ["# 保存したメモ\n"]
        for memo in memos:
            lines.append(f"## {memo['term']}")
            lines.append(f"{memo['note']}\n")
            lines.append(f"_保存日時: {memo.get('created_at', 'N/A')}_\n")
            lines.append("---\n")

        return "\n".join(lines)
