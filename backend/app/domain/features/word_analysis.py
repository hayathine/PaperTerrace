import os
from concurrent.futures import ThreadPoolExecutor

from app.providers import RedisService, get_ai_provider
from app.providers.dictionary_provider import get_dictionary_provider
from common.logger import ServiceLogger
from common.utils.text import truncate_context

from .correspondence_lang_dict import SUPPORTED_LANGUAGES

log = ServiceLogger("WordAnalysis")


class WordAnalysisService:
    def __init__(self):
        from app.domain.services.local_translator import get_local_translator

        self.ai_provider = get_ai_provider()
        self.dict_provider = get_dictionary_provider()
        self.local_translator = get_local_translator()
        self.redis = RedisService()
        self.translate_model = os.getenv("MODEL_TRANSLATE", "gemini-2.5-flash-lite")
        self.executor = ThreadPoolExecutor(max_workers=4)

        self.word_cache = {}  # lemma -> bool (exists in dictionary)
        self.translation_cache = {}  # lemma -> translation

    async def translate(
        self,
        lemma: str,
        lang: str = "ja",
        context: str | None = None,
        session_id: str | None = None,
    ) -> dict | None:
        # 3.5 Local Machine Translation (M2M100) - ServiceB経由
        try:
            # translate_async は (translated_text, model_name, lemma) のタプルを返す
            (
                local_translation,
                _model,
                _lemma,
            ) = await self.local_translator.translate_async(lemma, tgt_lang=lang)
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
            log.warning(
                "translate",
                "ServiceB translation failed",
                lemma=lemma,
                error=str(e),
            )

        # 4. AI Translation (Context-aware if context provided)
        if context:
            return await self.translate_with_context(
                lemma, context, lang, session_id=session_id
            )

        return None

    # geminiを用いた翻訳
    async def translate_with_context(
        self,
        word: str,
        context: str,
        lang: str = "ja",
        user_id: str | None = None,
        session_id: str | None = None,
    ) -> dict | None:
        """
        Translate word using document context.
        """
        max_context_length = int(os.getenv("MAX_CONTEXT_LENGTH", "800"))
        truncated = truncate_context(context, word, max_context_length)
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        try:
            from common.dspy.config import setup_dspy
            from common.dspy.modules import WordTranslationModule
            from common.dspy.trace import TraceContext, trace_dspy_call

            setup_dspy()
            trans_mod = WordTranslationModule()
            res, trace_id = await trace_dspy_call(
                "WordTranslationModule",
                "WordTranslationInContext",
                trans_mod,
                {
                    "target_word": word,
                    "context": truncated,
                    "lang_name": lang_name,
                },
                context=TraceContext(user_id=user_id, session_id=session_id),
            )
            translation = res.translation.strip()

            self.translation_cache[word] = translation
            self.redis.set(f"trans:{lang}:{word}", translation, expire=604800)

            return {
                "word": word,
                "translation": translation,
                "source": "Gemini (Context)",
                "trace_id": trace_id,
            }
        except Exception as e:
            log.error(
                "translate_with_context",
                "Context translation failed",
                word=word,
                error=str(e),
            )

            return None
