import asyncio
import os
import re
import sqlite3
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
jam = Jamdict()
api_key = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=api_key)


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
        self.word_cache = {}

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
                if token.is_punct or token.is_space:
                    p_tokens_html.append(f"<span>{token.text}</span>")
                    continue

                lemma = token.lemma_.lower()
                if lemma not in self.word_cache:
                    res = await loop.run_in_executor(executor, jam.lookup, lemma)
                    self.word_cache[lemma] = len(res.entries) > 0

                color = (
                    "border-indigo-200 hover:bg-indigo-100"
                    if self.word_cache[lemma]
                    else "border-purple-200 hover:bg-purple-100"
                )
                p_tokens_html.append(
                    f'<span class="cursor-pointer border-b {color} inline\
                        " hx-get="/explain/{lemma}" \
                            hx-target="#definition-box">{token.text}</span>'
                )

            yield f'data: <p class="mb-6">{"".join(p_tokens_html)}</p>\n\n'

    async def explain_word(self, lemma: str) -> str:
        lookup_res = jam.lookup(lemma)
        if lookup_res.entries:
            ja = [
                e.kanji_forms[0].text if e.kanji_forms else e.kana_forms[0].text
                for e in lookup_res.entries[:3]
            ]
            return self._format_bubble(lemma, " / ".join(list(dict.fromkeys(ja))), "Jamdict")

        prompt = f"英単語「{lemma}」の日本語訳を3つ程度簡潔に。"
        res = self.client.models.generate_content(model=self.model, contents=prompt)
        return self._format_bubble(lemma, res.text.strip(), "Gemini")

    def _format_bubble(self, word, definition, source):
        bg = "bg-blue-50" if source == "Jamdict" else "bg-purple-50"
        return f'<div class="p-4 rounded-lg {bg} border animate-in"><b>{word}</b>\
            <p>{definition}</p><small>{source}</small></div>'
