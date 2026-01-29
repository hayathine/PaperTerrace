import os
import sqlite3

import requests

from src.logger import logger

# Public domain EJDict file URL (kujirahand/EJDict)
# Public domain EJDict file URL (kujirahand/EJDict)
EJDICT_URL = (
    "https://raw.githubusercontent.com/kujirahand/EJDict/master/release/ejdict-hand-utf8.txt"
)
DB_PATH = "ejdict.sqlite3"


class DictionaryProvider:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self._ensure_db_initialized()

    def _get_connection(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path)

    def _ensure_db_initialized(self):
        """Check if DB exists, if not create and populate it."""
        if os.path.exists(self.db_path):
            return

        logger.info("Initializing EJDict database...")
        try:
            self._create_tables()
            self._populate_db()
            logger.info("EJDict database initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize EJDict database: {e}")
            if os.path.exists(self.db_path):
                os.remove(self.db_path)  # Cleanup corrupt file
            raise

    def _create_tables(self):
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS items (
                    word TEXT PRIMARY KEY,
                    mean TEXT
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_word ON items(word)")

    def _populate_db(self):
        """Download and insert dictionary data."""
        import string

        base_url = "https://raw.githubusercontent.com/kujirahand/EJDict/master/src/{char}.txt"
        data = []

        logger.info("Downloading dictionary data (a-z)...")

        # Download a-z files
        # Using a session for connection reuse
        with requests.Session() as session:
            for char in string.ascii_lowercase:
                url = base_url.format(char=char)
                try:
                    response = session.get(url)
                    response.raise_for_status()
                    content = response.text

                    for line in content.splitlines():
                        if "\t" in line:
                            parts = line.split("\t", 1)
                            if len(parts) == 2:
                                word, mean = parts
                                data.append((word, mean))

                    logger.info(f"Downloaded {char}.txt")
                except requests.RequestException as e:
                    logger.error(f"Failed to download {char}.txt: {e}")
                    # Continue best effort? Or fail?
                    # If we miss 'a', dictionary is useless. Better fail.
                    raise RuntimeError(f"Failed to download dictionary data for {char}: {e}")

        logger.info(f"Inserting {len(data)} words into database...")
        with self._get_connection() as conn:
            conn.executemany("INSERT OR IGNORE INTO items (word, mean) VALUES (?, ?)", data)
            conn.commit()

    def lookup(self, word: str) -> str | None:
        """Look up a word definition. Returns None if not found."""
        if not word:
            return None

        word = word.strip().lower()  # EJDict keys are mostly lowercase, or we should check?
        # Actually EJDict has mixed case but mostly lower for common words.
        # Let's try exact match first, then lower.

        with self._get_connection() as conn:
            # 1. Exact match
            row = conn.execute("SELECT mean FROM items WHERE word = ?", (word,)).fetchone()
            if row:
                return row[0]

            # 2. Lowercase match (if input was not already lower)
            if word != word.lower():
                row = conn.execute(
                    "SELECT mean FROM items WHERE word = ?", (word.lower(),)
                ).fetchone()
                if row:
                    return row[0]

            return None


# Singleton
_instance = None


def get_dictionary_provider():
    global _instance
    if _instance is None:
        _instance = DictionaryProvider()
    return _instance


if __name__ == "__main__":
    # Test run
    provider = DictionaryProvider()
    print(provider.lookup("apple"))
