# src/history.py
import json
import sqlite3
from datetime import datetime

from src.base_model import History, User
from src.logger import logger

DB_PATH = "furigana.db"


class HistoryManager:
    """
    word: クリックした単語（辞書形/lemma）
    explain: 取得した説明文（リスト形式）
    source: 参照元（WordNet か Jamdict か）
    created_at: 保存日時（ISO 8601形式。FirestoreのTimestampと相性が良い）
    user_id: ユーザー識別子（将来的な認証機能導入に備えて）
    """

    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._create_table()

    def _create_table(self):
        with sqlite3.connect(self.db_path) as conn:
            # 履歴テーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    word TEXT NOT NULL,
                    explain TEXT,  -- JSON形式で保存
                    source TEXT,
                    birthday TEXT,
                    created_at TEXT,
                    user_id TEXT DEFAULT 'guest'
                )
            """)
        logger.info("History table ensured in database.")

    def regester_history(self, history: History):
        # Firestoreへの移行を考え、リストはJSON文字列として保存
        def_json = json.dumps(history.explain, ensure_ascii=False)
        timestamp = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO history (word, explain, source, created_at, user_id) 
                VALUES (?, ?, ?, ?, ?)""",
                (history.word, def_json, history.source, timestamp, "guest"),
            )
            logger.info(
                f"Saved history: {history.word} from {history.source} at {timestamp}"
            )
            conn.commit()

    def get_history(self, limit: int = 10) -> list[str]:
        """直近に検索した単語のリストを取得する"""
        with sqlite3.connect(self.db_path) as conn:
            # 重複を除いて、新しい順に取得
            cur = conn.execute(
                "SELECT DISTINCT word FROM history ORDER BY id DESC LIMIT ?", (limit,)
            )
            rows = cur.fetchall()
            return [row[0] for row in rows]


history_manager = HistoryManager()


class UserManager:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        self._create_table()

    def _create_table(self):
        with sqlite3.connect(self.db_path) as conn:
            # ユーザーテーブル
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT UNIQUE NOT NULL,
                    nickname TEXT,
                    birthday TEXT,
                    created_at TEXT
                )
            """)
        logger.info("User table ensured in database.")

    def get_user_nickname(self, user: User) -> str | None:
        """ユーザーIDからニックネームを取得する"""
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.execute(
                "SELECT nickname FROM users WHERE user_id = ?", (user.user_id,)
            )
            row = cur.fetchone()
            return row[0] if row else None

    def register_user(self, user: User):
        """ユーザー情報を登録・更新する"""
        timestamp = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                    INSERT INTO users (user_id, nickname, birthday, created_at)
                    VALUES (?, ?, ?, ?)
                    ON CONFLICT(user_id) DO UPDATE SET
                        nickname=excluded.nickname,
                        birthday=excluded.birthday
                """,
                (user.user_id, user.nickname, user.birthday, timestamp),
            )

            logger.info(f"Registered/Updated user: {user.user_id} at {timestamp}")
            conn.commit()


user_manager = UserManager()
