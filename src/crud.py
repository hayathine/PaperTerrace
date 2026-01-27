import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "ocr_reader.db")


def get_ocr_from_db(file_hash: str) -> str | None:
    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            "SELECT ocr_text FROM ocr_reader WHERE file_hash = ?", (file_hash,)
        ).fetchone()
        if row:
            return row[0]


def save_ocr_to_db(
    file_hash: str,
    filename: str,
    ocr_text: str,
    model_name: str = "unknown",
) -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            "INSERT INTO ocr_reader (file_hash, filename, ocr_text, model_name, created_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
            (file_hash, filename, ocr_text, model_name),
        )
