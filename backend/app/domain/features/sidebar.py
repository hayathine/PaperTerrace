"""
sidebarに用語やノートを表示・保存する機能を提供するモジュール

ノートの保存先・キャッシュ戦略:
- 登録ユーザー: Cloud SQL に永続保存 + Redis に読み取りキャッシュ (write-invalidate)
- ゲスト:       Redis にセッション限定で一時保存 (TTL: 1時間)

キャッシュキー設計:
  guest_notes:{session_id}          → ゲストのノート一覧 (list[dict])
  guest_note_session:{note_id}      → note_id から session_id への逆引き
  user_notes:{user_id}:{paper_id}   → 登録ユーザーの読み取りキャッシュ
"""

import uuid6
from datetime import datetime

from app.providers import get_storage_provider
from common.logger import logger
from redis_provider.provider import RedisService

# 他のセッションデータ (session:*, task:*) と同じ1時間に合わせる
_SESSION_TTL = 3600


def _guest_notes_key(session_id: str) -> str:
    return f"guest_notes:{session_id}"


def _guest_note_session_key(note_id: str) -> str:
    """note_id → session_id の逆引き (ゲストノート削除時に使用)"""
    return f"guest_note_session:{note_id}"


def _user_notes_cache_key(user_id: str, paper_id: str | None) -> str:
    return f"user_notes:{user_id}:{paper_id or 'all'}"


class NoteError(Exception):
    """Note-specific exception."""

    pass


class SidebarNoteService:
    """Sidebar note service for storing notes and terms."""

    def __init__(self):
        self.storage = get_storage_provider()
        self.cache = RedisService()

    def _is_registered(self, user_id: str | None) -> bool:
        """ユーザーがDBに登録済みかどうかを確認する。"""
        if not user_id:
            return False
        return bool(self.storage.get_user(user_id))

    # ------------------------------------------------------------------ #
    # ゲスト向け Redis 操作                                               #
    # ------------------------------------------------------------------ #

    def _add_guest_note(self, session_id: str, note_dict: dict) -> None:
        """ゲストノートをRedisに一時保存する。"""
        note_id = note_dict["note_id"]
        key = _guest_notes_key(session_id)

        notes: list[dict] = self.cache.get(key) or []
        # 同一 note_id が既にある場合は差し替え (upsert)
        notes = [n for n in notes if n.get("note_id") != note_id]
        notes.insert(0, note_dict)

        self.cache.set(key, notes, expire=_SESSION_TTL)
        # delete 時に session_id を逆引きできるように保存
        self.cache.set(_guest_note_session_key(note_id), session_id, expire=_SESSION_TTL)

    def _get_guest_notes(self, session_id: str, paper_id: str | None = None) -> list[dict]:
        """Redisからゲストノートを取得する。"""
        notes: list[dict] = self.cache.get(_guest_notes_key(session_id)) or []
        if paper_id:
            notes = [n for n in notes if n.get("paper_id") == paper_id]
        return notes

    def _delete_guest_note(self, note_id: str) -> bool:
        """Redisからゲストノートを削除する。"""
        session_id = self.cache.get(_guest_note_session_key(note_id))
        if not session_id:
            return False

        key = _guest_notes_key(session_id)
        notes: list[dict] = self.cache.get(key) or []
        filtered = [n for n in notes if n.get("note_id") != note_id]

        if len(filtered) == len(notes):
            return False

        self.cache.set(key, filtered, expire=_SESSION_TTL)
        self.cache.delete(_guest_note_session_key(note_id))
        return True

    # ------------------------------------------------------------------ #
    # 登録ユーザー向け Redis キャッシュ操作                              #
    # ------------------------------------------------------------------ #

    def _invalidate_user_cache(self, user_id: str, paper_id: str | None) -> None:
        """書き込み・削除後に読み取りキャッシュを無効化する。"""
        self.cache.delete(_user_notes_cache_key(user_id, paper_id))
        # paper_id 指定なし (全件) のキャッシュも同時に破棄
        self.cache.delete(_user_notes_cache_key(user_id, None))

    def _get_cached_user_notes(
        self, user_id: str, paper_id: str | None
    ) -> list[dict] | None:
        """Redisキャッシュからノートを取得する。ミス時は None を返す。"""
        return self.cache.get(_user_notes_cache_key(user_id, paper_id))

    def _set_user_notes_cache(
        self, user_id: str, paper_id: str | None, notes: list[dict]
    ) -> None:
        """取得したノートをRedisにキャッシュする。"""
        self.cache.set(_user_notes_cache_key(user_id, paper_id), notes, expire=_SESSION_TTL)

    # ------------------------------------------------------------------ #
    # 公開インターフェース                                                #
    # ------------------------------------------------------------------ #

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
        note_id: str | None = None,
        paper_id: str | None = None,
    ) -> dict:
        """
        Add a note to the sidebar.
        If note_id is provided, it updates the existing note.

        Args:
            session_id: The session identifier
            term: The term or keyword
            note: The note content
            image_url: Optional image URL
            page_number: Page number for jump
            x: X coordinate (relative %)
            y: Y coordinate (relative %)
            user_id: Optional user identifier (if logged in)
            note_id: Optional existing note ID for update
            paper_id: Optional paper identifier

        Returns:
            The created/updated note with its ID
        """
        try:
            if not note_id:
                note_id = str(uuid6.uuid7())

            note_dict = {
                "note_id": note_id,
                "session_id": session_id,
                "paper_id": paper_id,
                "term": term,
                "note": note,
                "image_url": image_url,
                "page_number": page_number,
                "x": x,
                "y": y,
                "user_id": user_id,
                "created_at": datetime.now().isoformat(),
            }

            if self._is_registered(user_id):
                # 登録ユーザー: Cloud SQL に永続保存し、読み取りキャッシュを invalidate
                self.storage.save_note(
                    note_id, session_id, term, note,
                    image_url, page_number, x, y, user_id, paper_id,
                )
                self._invalidate_user_cache(user_id, paper_id)
                logger.info(
                    "Note added/updated (Persistent)",
                    extra={
                        "note_id": note_id,
                        "session_id": session_id,
                        "paper_id": paper_id,
                        "term": term,
                        "user_id": user_id,
                    },
                )
            else:
                # ゲスト: Redis にセッション限定で一時保存
                self._add_guest_note(session_id, note_dict)
                logger.info(
                    "Note added (Guest/Temporary)",
                    extra={
                        "note_id": note_id,
                        "session_id": session_id,
                        "paper_id": paper_id,
                        "term": term,
                    },
                )

            return note_dict
        except Exception as e:
            logger.exception(
                "Failed to add note",
                extra={"session_id": session_id, "paper_id": paper_id, "error": str(e)},
            )
            raise NoteError(f"ノートの保存に失敗しました: {e}") from e

    def get_notes(
        self, session_id: str, paper_id: str | None = None, user_id: str | None = None
    ) -> list[dict]:
        """
        Get all notes for a session or user.

        登録ユーザーはRedisキャッシュを優先し、ミス時のみCloud SQLに問い合わせる。

        Args:
            session_id: The session identifier
            paper_id: Optional paper identifier
            user_id: Optional user identifier

        Returns:
            List of notes
        """
        try:
            if self._is_registered(user_id):
                # キャッシュヒット: Cloud SQL へのアクセスを省略
                cached = self._get_cached_user_notes(user_id, paper_id)
                if cached is not None:
                    logger.info(
                        "Notes retrieved (cache hit)",
                        extra={"user_id": user_id, "paper_id": paper_id, "count": len(cached)},
                    )
                    return cached

                # キャッシュミス: Cloud SQL から取得してキャッシュに書き込む
                notes = self.storage.get_notes(session_id, paper_id=paper_id, user_id=user_id)
                self._set_user_notes_cache(user_id, paper_id, notes)
                logger.info(
                    "Notes retrieved (cache miss → DB)",
                    extra={"user_id": user_id, "paper_id": paper_id, "count": len(notes)},
                )
            else:
                notes = self._get_guest_notes(session_id, paper_id=paper_id)
                logger.info(
                    "Notes retrieved (guest/Redis)",
                    extra={"session_id": session_id, "paper_id": paper_id, "count": len(notes)},
                )

            return notes
        except Exception as e:
            logger.exception(
                "Failed to retrieve notes",
                extra={"session_id": session_id, "paper_id": paper_id, "error": str(e)},
            )
            return []

    def delete_note(self, note_id: str, user_id: str | None = None, paper_id: str | None = None) -> bool:
        """
        Delete a note.

        Args:
            note_id: The note identifier
            user_id: Optional user identifier (登録ユーザーはキャッシュ invalidate に使用)
            paper_id: Optional paper identifier (同上)

        Returns:
            True if deleted, False otherwise
        """
        try:
            # まずRedis (ゲストノート) を試みる
            deleted = self._delete_guest_note(note_id)
            if not deleted:
                # DB (登録ユーザーノート) を削除し、キャッシュを invalidate
                deleted = self.storage.delete_note(note_id)
                if deleted and user_id:
                    self._invalidate_user_cache(user_id, paper_id)

            if deleted:
                logger.info("Note deleted", extra={"note_id": note_id})
            else:
                logger.warning("Note not found for deletion", extra={"note_id": note_id})
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
