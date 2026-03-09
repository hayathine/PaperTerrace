import logging
import os
from functools import lru_cache

import spacy

logger = logging.getLogger(__name__)

# サーバー上のモデルパス（デフォルトは /app/models/en_core_web_sm/）
SPACY_MODEL_PATH = os.getenv("SPACY_MODEL_PATH", "/app/models/en_core_web_sm/")

try:
    # ローカルパスからモデルをロード
    if os.path.exists(SPACY_MODEL_PATH):
        nlp = spacy.load(SPACY_MODEL_PATH, disable=["ner"])
        logger.info(
            f"Loaded spaCy model from local path: {SPACY_MODEL_PATH} (with parser)"
        )
    else:
        # パッケージとしてのロードを試みる（フォールバック）
        nlp = spacy.load("en_core_web_sm", disable=["ner"])
        logger.info("Loaded spaCy model: en_core_web_sm (package)")
except OSError:
    try:
        # parserも無効にして試行
        nlp = spacy.load(SPACY_MODEL_PATH, disable=["ner", "parser"])
        logger.info(
            f"Loaded spaCy model from local path: {SPACY_MODEL_PATH} (fallback)"
        )
    except OSError:
        logger.error(f"No spaCy model found at {SPACY_MODEL_PATH} or as package.")
        nlp = None


class NLPService:
    """Service to handle NLP tasks like lemmatization on the inference side."""

    @staticmethod
    @lru_cache(maxsize=5000)
    def lemmatize(text: str) -> str:
        """Get lemma for text using Spacy model."""
        if nlp is None:
            return text.strip().lower()

        text = text.strip()
        if not text:
            return ""

        # Lowercase for better normalization
        doc = nlp(text.lower())
        return " ".join([token.lemma_.lower() for token in doc])

    @staticmethod
    def is_single_word(text: str) -> bool:
        """Heuristic to check if the input is likely a single word."""
        return len(text.strip().split()) == 1

    @staticmethod
    def tokenize(text: str) -> list[dict]:
        """Tokenize text into a list of word/lemma info."""
        if nlp is None:
            # Fallback
            words = text.split()
            return [
                {
                    "text": w,
                    "lemma": w.lower(),
                    "ws": " ",
                    "is_punct": False,
                    "is_space": False,
                }
                for w in words
            ]

        text = text.strip()
        if not text:
            return []

        doc = nlp(text)
        results = []
        for token in doc:
            results.append(
                {
                    "text": token.text,
                    "lemma": token.lemma_.lower(),
                    "ws": token.whitespace_,
                    "is_punct": token.is_punct,
                    "is_space": token.is_space,
                }
            )
        return results
