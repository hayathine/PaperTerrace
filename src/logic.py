import asyncio
import os
import re
import sqlite3
import threading
from concurrent.futures import ThreadPoolExecutor

import spacy
from dotenv import load_dotenv
from google import genai
from google.genai import types
from jamdict import Jamdict

from src.crud import get_ocr_from_db, save_ocr_to_db
from src.logger import logger
from src.utils import _get_file_hash

# 共通設定
load_dotenv()
DB_PATH = os.getenv("DB_PATH") or "ocr_reader.db"
executor = ThreadPoolExecutor(max_workers=4)
nlp = spacy.load("en_core_web_lg", disable=["ner", "parser", "tok2vec"])
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)

# Thread-local storage for Jamdict instances
_thread_local = threading.local()


def _get_jam() -> Jamdict:
    """Get a thread-local Jamdict instance."""
    if not hasattr(_thread_local, "jam"):
        _thread_local.jam = Jamdict()
    return _thread_local.jam


def _lookup_word(lemma: str) -> bool:
    """Thread-safe word lookup."""
    jam = _get_jam()
    res = jam.lookup(lemma)
    return len(res.entries) > 0


def _lookup_word_full(lemma: str):
    """Thread-safe full word lookup for explain."""
    jam = _get_jam()
    return jam.lookup(lemma)


class PDFOCRService:
    def __init__(self, model):
        self.client = client
        self.model = model
        self._init_db()

    def _init_db(self):
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

    async def extract_text_with_ai(self, file_bytes: bytes, filename: str = "unknown.pdf") -> str:
        file_hash = _get_file_hash(file_bytes)
        cached_ocr = get_ocr_from_db(file_hash)
        if cached_ocr:
            logger.info("Returning cached OCR text.")
            return cached_ocr

        logger.info(f"--- AI OCR Processing: {filename} ---")
        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=[
                    types.Part.from_bytes(data=file_bytes, mime_type="application/pdf"),
                    "このPDFのテキストを構造を維持して文字起こししてください。",
                ],
            )
            ocr_text = response.text.strip()
        except Exception as e:
            logger.error(f"OCR extraction failed: {e}")
            return f"ERROR_API_FAILED: {str(e)}"
        save_ocr_to_db(
            file_hash=file_hash,
            filename=filename,
            ocr_text=ocr_text,
            model_name=self.model,
        )
        logger.info("OCR extraction completed and saved to database.")
        return ocr_text


class EnglishAnalysisService:
    def __init__(self):
        self.client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        self.model = os.getenv("OCR_MODEL") or "gemini-1.5-flash"
        self.ocr_service = PDFOCRService(self.model)
        self.word_cache = {}  # lemma -> bool (jamdict にあるかどうか)
        self.translation_cache = {}  # lemma -> translation (Gemini翻訳キャッシュ)
        self._unknown_words = set()  # Jamdictにない単語を収集

    async def tokenize_stream(self, text: str):
        paragraphs = re.split(r"\n{2,}", text.replace("\r\n", "\n"))
        loop = asyncio.get_event_loop()

        for p_text in paragraphs:
            p_text = p_text.replace("\n", " ").strip()
            if not p_text:
                continue

            doc = await loop.run_in_executor(executor, nlp, p_text)
            p_tokens_html = []

            for token in doc:
                # トークン後のスペースを取得
                whitespace = token.whitespace_

                if token.is_punct or token.is_space:
                    p_tokens_html.append(f"<span>{token.text}</span>{whitespace}")
                    continue

                lemma = token.lemma_.lower()
                if lemma not in self.word_cache:
                    self.word_cache[lemma] = await loop.run_in_executor(
                        executor, _lookup_word, lemma
                    )
                    # Jamdictにない単語を収集
                    if not self.word_cache[lemma]:
                        self._unknown_words.add(lemma)

                color = (
                    "border-indigo-200 hover:bg-indigo-100"
                    if self.word_cache[lemma]
                    else "border-purple-200 hover:bg-purple-100"
                )
                p_tokens_html.append(
                    f'<span class="cursor-pointer border-b {color} inline'
                    f'" hx-get="/explain/{lemma}" '
                    f'hx-target="#definition-box">{token.text}</span>{whitespace}'
                )

            yield f'data: <p class="mb-6">{"".join(p_tokens_html)}</p>\n\n'

        # ストリーム終了時に未知の単語をバッチ翻訳
        if self._unknown_words:
            logger.info(f"Batch translation starting with {len(self._unknown_words)} words")
            translations = await self._batch_translate_words(
                list(self._unknown_words)[: int(os.getenv("BATCH_WORD_LIMIT", "50"))]
            )
            # 結果を translation_cache に統合
            self.translation_cache.update(translations)
            self._unknown_words.clear()

    async def _batch_translate_words(self, words: list[str]) -> dict[str, str]:
        """未知の単語を一括でGeminiで翻訳して辞書として返す"""
        logger.info(f"Batch translation starting with {len(words)} words")
        result: dict[str, str] = {}

        if not words:
            return result

        # 既にキャッシュにある単語は除外
        words_to_translate = [w for w in words if w not in self.translation_cache]
        if not words_to_translate:
            return result

        # バッチプロンプトを作成
        words_list = "\n".join(f"- {w}" for w in words_to_translate)
        prompt = f"""以下の英単語それぞれの日本語訳を1〜2語で簡潔に答えてください。
フォーマット: 単語: 訳

{words_list}"""

        try:
            res = self.client.models.generate_content(model=self.model, contents=prompt)
            response_text = res.text.strip()

            # レスポンスをパース
            for line in response_text.split("\n"):
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        word = parts[0].strip().lower().lstrip("- ")
                        translation = parts[1].strip()
                        if word and translation:
                            result[word] = translation
            logger.info(f"Batch translation completed with {len(result)} words")
        except Exception as e:
            logger.error(f"Batch translation failed: {e}")

        return result

    def get_translation(self, lemma: str) -> dict | None:
        """キャッシュから翻訳を取得する。Jamdictにある場合はNone、翻訳がある場合はdictを返す"""
        # word_cache をチェック - Jamdict にある場合は None を返す（Jamdictで処理する）
        if lemma in self.word_cache:
            if self.word_cache[lemma]:
                # Jamdict にある → None を返して別途 Jamdict で処理させる
                return None
            else:
                # Jamdict にない → translation_cache を確認
                if lemma in self.translation_cache:
                    return {
                        "word": lemma,
                        "translation": self.translation_cache[lemma],
                        "source": "Gemini (cached)",
                    }
        return None

    def get_word_cache(self) -> dict[str, bool]:
        """word_cache を取得"""
        return self.word_cache

    def get_translation_cache(self) -> dict[str, str]:
        """translation_cache を取得"""
        return self.translation_cache
