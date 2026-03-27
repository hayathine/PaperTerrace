
from concurrent.futures import ThreadPoolExecutor

from app.providers import RedisService, get_ai_provider
from app.providers.dictionary_provider import get_dictionary_provider
from common.config import settings
from common.logger import ServiceLogger
from common.utils.text import truncate_context

from .correspondence_lang_dict import SUPPORTED_LANGUAGES

log = ServiceLogger("WordAnalysis")


class WordAnalysisService:
    def __init__(self):
        self.ai_provider = get_ai_provider()
        self.dict_provider = get_dictionary_provider()
        self.redis = RedisService()
        self.translate_model = settings.get("MODEL_TRANSLATE", "gemini-2.5-flash-lite")
        self.executor = ThreadPoolExecutor(max_workers=4)

        self.word_cache = {}  # lemma -> bool (exists in dictionary)
        self.translation_cache = {}  # lemma -> translation

    async def translate(
        self,
        lemma: str,
        lang: str = "ja",
        context: str | None = None,
        session_id: str | None = None,
        paper_title: str | None = None,
    ) -> dict | None:
        # ... logic
        
        # 2. Translation Pod 翻訳
        from app.providers.inference_client import get_inference_client
        inf_client = await get_inference_client()
        
        if not inf_client.translate_disabled:
            # 長文やフレーズ(スペースあり)は Gemini に任せ、単語のみ Translation Pod を使用する
            is_phrase = " " in lemma.strip()
            is_too_long = len(lemma) > 25

            if is_phrase or is_too_long:
                log.debug("translate", "長文またはフレーズのため Translation Pod をスキップします", word=lemma)
            else:
                try:
                    # 80 トークン制限に合わせ、タイトル・文脈を極限まで切り詰める
                    # lemma > 10 char の場合は、LLMのリソース節約のためコンテキストをスキップする
                    safe_title = (paper_title[:60] + "...") if paper_title and len(paper_title) > 65 else paper_title
                    input_context = (safe_title if safe_title else (context[:30] if context else None)) if len(lemma) <= 10 else None
                    
                    log.info("translate", "Translation AI 開始(64-token mode)", word=lemma, ctx=input_context)
                    translation = await inf_client.translate_text(
                        text=lemma,
                        tgt_lang=lang,
                        paper_context=input_context
                    )
                    if translation:
                        self.translation_cache[lemma] = translation
                        return {
                            "word": lemma,
                            "translation": translation,
                            "source": "Translation AI",
                        }
                except Exception as e:
                    log.warning("translate", "Translation Pod翻訳に失敗しました", error=str(e))

        # 3. Gemini Translation (Context-aware if context provided)
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
        max_context_length = int(settings.get("MAX_CONTEXT_LENGTH", "800"))
        truncated = truncate_context(context, word, max_context_length)
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        try:
            from common.dspy_utils.config import setup_dspy
            from common.dspy_utils.modules import SimpleTranslationModule
            from common.dspy_utils.trace import TraceContext, trace_dspy_call

            setup_dspy()
            trans_mod = SimpleTranslationModule()
            res, trace_id = await trace_dspy_call(
                "SimpleTranslationModule",
                "SimpleTranslation",
                trans_mod,
                {
                    "target_word": word,
                    "paper_context": truncated,
                    "user_persona": "Professional Translator",
                    "lang_name": lang_name,
                },
                context=TraceContext(user_id=user_id, session_id=session_id),
            )
            translation = res.translation.strip()

            self.translation_cache[word] = translation
            self.redis.set(f"trans:{lang}:{word}", translation, expire=604800)

            log.debug(
                "translate_with_context",
                "単語の翻訳が完了しました",
                word=word,
                translation=translation,
                trace_id=trace_id,
            )

            return {
                "word": word,
                "translation": translation,
                "source": "Gemini (Context)",
                "trace_id": trace_id,
            }
        except Exception as e:
            log.error(
                "translate_with_context",
                "文脈に応じた翻訳に失敗しました",
                word=word,
                error=str(e),
            )

            return None
