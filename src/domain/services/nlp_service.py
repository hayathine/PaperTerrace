import spacy

from src.core.logger import logger
from src.core.utils import get_memory_usage_mb

try:
    # Get lemma using parser for better accuracy
    mem_before = get_memory_usage_mb()
    nlp = spacy.load("en_core_web_sm", disable=["ner"])
    mem_after = get_memory_usage_mb()
    logger.info(
        f"Loaded spaCy model: en_core_web_sm (with parser). "
        f"Memory: {mem_before:.1f}MB -> {mem_after:.1f}MB (diff: {mem_after - mem_before:.1f}MB)"
    )
except OSError:
    try:
        # Fallback
        mem_before = get_memory_usage_mb()
        nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
        mem_after = get_memory_usage_mb()
        logger.info(
            f"Loaded spaCy model: en_core_web_sm (fallback). "
            f"Memory: {mem_before:.1f}MB -> {mem_after:.1f}MB (diff: {mem_after - mem_before:.1f}MB)"
        )
    except OSError:
        logger.error("No spaCy model found. Please run 'python -m spacy download en_core_web_sm'.")
        raise


class NLPService:
    @staticmethod
    def lemmatize(text: str) -> str:
        """Get lemma for text using Spacy model."""
        try:
            text = text.strip()
            if not text:
                return ""
            # Lowercase for better normalization
            doc = nlp(text.lower())
            return " ".join([token.lemma_.lower() for token in doc])
        except Exception as e:
            logger.error(f"[NLPService] Lemmatization failed for '{text}': {e}")
            return text.lower()  # Fallback to lowercase original if lemmatization fails

    @staticmethod
    def get_nlp():
        return nlp
