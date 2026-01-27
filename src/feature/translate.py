"""
Translation service for click-to-translate functionality.
Supports multiple target languages using AI provider.
"""

import os

from src.logger import logger
from src.providers import get_ai_provider

SUPPORTED_LANGUAGES = {
    "ja": "日本語",
    "en": "English",
    "zh": "中文",
    "ko": "한국어",
    "es": "Español",
    "fr": "Français",
    "de": "Deutsch",
}

DEFAULT_LANGUAGE = os.getenv("DEFAULT_TRANSLATION_LANGUAGE", "ja")


class TranslationService:
    """Translation service using AI provider."""

    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.cache: dict[str, str] = {}

    async def translate_word(
        self, word: str, target_lang: str = DEFAULT_LANGUAGE
    ) -> dict:
        """
        Translate a single word to the target language.
        
        Returns:
            dict with keys: word, translation, target_lang, source
        """
        cache_key = f"{word}:{target_lang}"
        if cache_key in self.cache:
            logger.info(f"Translation cache hit: {word} -> {target_lang}")
            return {
                "word": word,
                "translation": self.cache[cache_key],
                "target_lang": target_lang,
                "source": "cache",
            }

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        prompt = f"""Translate the English word or phrase "{word}" to {lang_name}.
Provide only the translation, nothing else. If it's a technical term, include a brief explanation in parentheses."""

        try:
            translation = await self.ai_provider.generate(prompt)
            self.cache[cache_key] = translation
            logger.info(f"Translated: {word} -> {translation} ({target_lang})")
            return {
                "word": word,
                "translation": translation,
                "target_lang": target_lang,
                "source": "ai",
            }
        except Exception as e:
            logger.error(f"Translation failed for '{word}': {e}")
            return {
                "word": word,
                "translation": f"翻訳エラー: {str(e)}",
                "target_lang": target_lang,
                "source": "error",
            }

    async def translate_phrase(
        self, phrase: str, target_lang: str = DEFAULT_LANGUAGE
    ) -> dict:
        """
        Translate a phrase or sentence to the target language.
        
        Returns:
            dict with keys: phrase, translation, target_lang, source
        """
        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        prompt = f"""Translate the following English text to {lang_name}:

"{phrase}"

Provide only the translation, maintaining the original meaning and nuance."""

        try:
            translation = await self.ai_provider.generate(prompt)
            logger.info(f"Phrase translated to {target_lang}")
            return {
                "phrase": phrase,
                "translation": translation,
                "target_lang": target_lang,
                "source": "ai",
            }
        except Exception as e:
            logger.error(f"Phrase translation failed: {e}")
            return {
                "phrase": phrase,
                "translation": f"翻訳エラー: {str(e)}",
                "target_lang": target_lang,
                "source": "error",
            }

    def get_supported_languages(self) -> dict[str, str]:
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES.copy()
