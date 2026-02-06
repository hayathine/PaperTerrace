import os
from concurrent.futures import ThreadPoolExecutor

from app.domain.prompts import (
    ANALYSIS_BATCH_TRANSLATE_PROMPT,
    ANALYSIS_WORD_TRANSLATE_CONTEXT_PROMPT,
    CORE_SYSTEM_PROMPT,
)
from app.domain.services.local_translator import get_local_translator
from common.logger import logger
from app.providers import RedisService, get_ai_provider
from app.providers.dictionary_provider import get_dictionary_provider
from app.utils import truncate_context

from .translate import SUPPORTED_LANGUAGES


class WordAnalysisService:
    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.dict_provider = get_dictionary_provider()
        self.local_translator = get_local_translator()
        self.redis = RedisService()
        self.translate_model = os.getenv("MODEL_TRANSLATE", "gemini-1.5-flash")
        self.executor = ThreadPoolExecutor(max_workers=4)

        self.word_cache = {}  # lemma -> bool (exists in dictionary)
        self.translation_cache = {}  # lemma -> translation

    async def lookup_or_translate(
        self, lemma: str, lang: str = "ja", context: str | None = None
    ) -> dict | None:
        """
        Lookup word in dictionary or translate it using AI.
        """
        # 1. Local Memory Cache
        if lemma in self.translation_cache:
            return {
                "word": lemma,
                "translation": self.translation_cache[lemma],
                "source": "Memory Cache",
            }

        # 2. Redis Cache
        cached_trans = self.redis.get(f"trans:{lang}:{lemma}")
        if cached_trans:
            self.translation_cache[lemma] = cached_trans
            return {
                "word": lemma,
                "translation": cached_trans,
                "source": "Redis Cache",
            }

        # 3.5 Local Machine Translation (M2M100) - ServiceB経由
        try:
            local_translation = await self.local_translator.translate_async(lemma)
            if (
                local_translation and local_translation != lemma
            ):  # 翻訳が成功し、元の単語と異なる場合
                self.word_cache[lemma] = False
                self.translation_cache[lemma] = local_translation
                self.redis.set(
                    f"trans:{lang}:{lemma}", local_translation, expire=604800
                )
                return {
                    "word": lemma,
                    "translation": local_translation,
                    "source": "ServiceB-MT",
                }
        except Exception as e:
            logger.warning(f"ServiceB translation failed for '{lemma}': {e}")

        # 4. AI Translation (Context-aware if context provided)
        if context:
            return await self.translate_with_context(lemma, context, lang)

        return None

    async def batch_translate(
        self, words: list[str], lang: str = "ja"
    ) -> dict[str, str]:
        """
        Batch translate multiple words.
        """
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        # Filter out already cached words
        words_to_translate = [w for w in words if w not in self.translation_cache]
        if not words_to_translate:
            return {}

        prompt = ANALYSIS_BATCH_TRANSLATE_PROMPT.format(
            lang_name=lang_name, words_list="\n".join(words_to_translate)
        )

        result = {}
        try:
            response_text = await self.ai_provider.generate(
                prompt,
                model=self.translate_model,
                system_instruction=CORE_SYSTEM_PROMPT,
            )

            for line in response_text.split("\n"):
                if ":" in line:
                    parts = line.split(":", 1)
                    if len(parts) == 2:
                        word = parts[0].strip().lower().lstrip("- ")
                        translation = parts[1].strip()
                        if word and translation:
                            result[word] = translation

            # Update caches
            self.translation_cache.update(result)
            for lemma, trans in result.items():
                self.redis.set(f"trans:{lang}:{lemma}", trans, expire=604800)

        except Exception as e:
            logger.error(f"Batch translation failed: {e}")

        return result

    async def translate_with_context(
        self, word: str, context: str, lang: str = "ja"
    ) -> dict | None:
        """
        Translate word using document context.
        """
        max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "800"))
        truncated = truncate_context(context, word, max_context_length)
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        prompt = ANALYSIS_WORD_TRANSLATE_CONTEXT_PROMPT.format(
            word=word, context=truncated, lang_name=lang_name
        )

        try:
            translation = await self.ai_provider.generate(
                prompt,
                model=self.translate_model,
                system_instruction=CORE_SYSTEM_PROMPT,
            )
            translation = translation.strip()

            self.translation_cache[word] = translation
            self.redis.set(f"trans:{lang}:{word}", translation, expire=604800)

            return {
                "word": word,
                "translation": translation,
                "source": "Gemini (Context)",
            }
        except Exception as e:
            logger.error(f"Context translation failed for '{word}': {e}")
            return None
