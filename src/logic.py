import hashlib
import os
import sqlite3

import genai
from google.genai import types

# データベースの初期化
DB_PATH = os.getenv("DB_PATH") or "ocr_reader.db"


class PDFOCRService:
    def __init__(self, client, model):
        self.client = client
        self.model = model
        self._init_db()

    def _init_db(self):
        """SQLiteのテーブル作成（将来の拡張性を考慮した設計）"""
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS ocr_reader (
                    file_hash TEXT PRIMARY KEY,
                    filename TEXT,
                    ocr_text TEXT,
                    model_name TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get_file_hash(self, file_bytes: bytes) -> str:
        return hashlib.sha256(file_bytes).hexdigest()

    async def extract_text_with_ai(
        self, file_bytes: bytes, filename: str = "unknown.pdf"
    ) -> str:
        """DBキャッシュをチェックし、なければGeminiでOCRを実行"""
        file_hash = self.get_file_hash(file_bytes)

        # 1. DBキャッシュの確認
        with sqlite3.connect(DB_PATH) as conn:
            row = conn.execute(
                "SELECT ocr_text FROM ocr_reader WHERE file_hash = ?", (file_hash,)
            ).fetchone()

            if row:
                print(f"--- DB Cache Hit: {filename} ({file_hash[:8]}) ---")
                return row[0]

        # 2. キャッシュがない場合はGeminiでOCR
        print(f"--- AI OCR Processing: {filename} ---")
        response = self.client.models.generate_content(
            model=self.model,
            contents=[
                types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"),
                "このPDFのテキストを構造を維持して文字起こししてください。",
            ],
        )
        ocr_text = response.text.strip()

        # 3. DBへ保存
        with sqlite3.connect(DB_PATH) as conn:
            conn.execute(
                "INSERT INTO ocr_reader (file_hash, filename, ocr_text, model_name)\
                      VALUES (?, ?, ?, ?)",
                (file_hash, filename, ocr_text, self.model),
            )
            conn.commit()

        return ocr_text


# EnglishAnalysisService 内での呼び出し
class EnglishAnalysisService:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = os.getenv("OCR_MODEL") or "gemini-1.5-flash"
        self.ocr_service = PDFOCRService(self.client, self.model)
        self.word_cache = {}
