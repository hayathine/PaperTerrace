import spacy

from src.core.logger import logger

try:
    # Get lemma using parser for better accuracy
    nlp = spacy.load("en_core_web_sm", disable=["ner"])
    logger.info("Loaded spaCy model: en_core_web_sm (with parser for better lemmatization)")
except OSError:
    try:
        # Fallback
        nlp = spacy.load("en_core_web_sm", disable=["ner", "parser"])
        logger.info("Loaded spaCy model: en_core_web_sm (fallback)")
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
