"""
翻訳機能を提供するモジュール
複数言語対応、キャッシュ機能付き
"""

import os

from src.logger import logger
from src.prompts import (
    SYSTEM_PROMPT,
    TRANSLATE_GENERAL_PROMPT,
    TRANSLATE_PHRASE_GENERAL_PROMPT,
)
from src.providers import get_ai_provider


class TranslationError(Exception):
    """Translation-specific exception."""

    pass


# 対応言語
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

    async def translate_word(self, word: str, target_lang: str = DEFAULT_LANGUAGE) -> dict:
        """
        Translate a single word to the target language.

        Returns:
            dict with keys: word, translation, target_lang, source
        """
        cache_key = f"{word}:{target_lang}"
        if cache_key in self.cache:
            logger.info(
                "Translation cache hit",
                extra={"word": word, "target_lang": target_lang, "cached": True},
            )
            return {
                "word": word,
                "translation": self.cache[cache_key],
                "target_lang": target_lang,
                "source": "cache",
            }

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        prompt = TRANSLATE_GENERAL_PROMPT.format(word=word, lang_name=lang_name)

        try:
            logger.debug(f"Translating word: '{word}' to {target_lang}")
            translation = await self.ai_provider.generate(prompt, system_instruction=SYSTEM_PROMPT)
            translation = translation.strip()

            if not translation:
                logger.warning(f"Empty translation result for '{word}'")
                raise TranslationError("Empty translation result")

            # Cache the result
            self.cache[cache_key] = translation
            logger.info(
                "Translation completed",
                extra={"word": word, "target_lang": target_lang, "cached": False},
            )

            return {
                "word": word,
                "translation": translation,
                "target_lang": target_lang,
                "source": "ai",
            }
        except TranslationError:
            raise
        except Exception as e:
            logger.exception(
                f"Translation failed for '{word}'",
                extra={"word": word, "target_lang": target_lang, "error": str(e)},
            )
            return {
                "word": word,
                "translation": f"翻訳エラー: {e}",
                "target_lang": target_lang,
                "source": "error",
            }

    async def translate_phrase(self, phrase: str, target_lang: str = DEFAULT_LANGUAGE) -> dict:
        """
        Translate a phrase or sentence to the target language.

        Returns:
            dict with keys: phrase, translation, target_lang, source
        """
        cache_key = f"phrase:{phrase}:{target_lang}"
        if cache_key in self.cache:
            logger.info(
                "Phrase translation cache hit",
                extra={"target_lang": target_lang, "phrase_length": len(phrase), "cached": True},
            )
            return {
                "phrase": phrase,
                "translation": self.cache[cache_key],
                "target_lang": target_lang,
                "source": "cache",
            }

        lang_name = SUPPORTED_LANGUAGES.get(target_lang, target_lang)
        prompt = TRANSLATE_PHRASE_GENERAL_PROMPT.format(phrase=phrase, lang_name=lang_name)

        try:
            logger.debug(f"Translating phrase of {len(phrase)} chars to {target_lang}")
            translation = await self.ai_provider.generate(prompt, system_instruction=SYSTEM_PROMPT)
            translation = translation.strip()

            if not translation:
                logger.warning("Empty phrase translation result")
                raise TranslationError("Empty translation result")

            # Cache the result
            self.cache[cache_key] = translation
            logger.info(
                "Phrase translation completed",
                extra={"target_lang": target_lang, "phrase_length": len(phrase), "cached": False},
            )

            return {
                "phrase": phrase,
                "translation": translation,
                "target_lang": target_lang,
                "source": "ai",
            }
        except TranslationError:
            raise
        except Exception as e:
            logger.exception(
                "Phrase translation failed",
                extra={"target_lang": target_lang, "error": str(e)},
            )
            return {
                "phrase": phrase,
                "translation": f"翻訳エラー: {e}",
                "target_lang": target_lang,
                "source": "error",
            }

    def get_supported_languages(self) -> dict[str, str]:
        """Return list of supported languages."""
        return SUPPORTED_LANGUAGES.copy()
