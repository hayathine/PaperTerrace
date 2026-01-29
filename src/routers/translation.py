"""
Translation Router
Handles word translation, explanation, and language settings.
"""

import asyncio

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..features import TranslationService
from ..logger import logger
from ..logic import executor
from ..providers import get_storage_provider
from ..services.analysis_service import EnglishAnalysisService

router = APIRouter(tags=["Translation"])

# Services
service = EnglishAnalysisService()
translation_service = TranslationService()
storage = get_storage_provider()


class LanguageSettingRequest(BaseModel):
    session_id: str
    language: str


@router.get("/translate/{word}")
async def translate_word(word: str, lang: str = "ja"):
    result = await translation_service.translate_word(word, lang)
    return JSONResponse(result)


@router.get("/explain/{word}")
async def explain(word: str, lang: str = "ja"):
    """Word explanation (Lemmatize -> Cache -> Jamdict -> Gemini)"""
    loop = asyncio.get_event_loop()

    # 0. Lemmatize input (Backend side now)
    # Spacy handles basic punctuation stripping usually, but we clean excessive stuff
    clean_input = word.replace("\n", " ").strip(" .,;!?(){}[\]\"'")
    if not clean_input:
        clean_input = word.strip()

    lemma = await loop.run_in_executor(executor, service.lemmatize, clean_input)
    original_word = word

    # logger.info(f"[explain] word='{word}' -> lemma='{lemma}'")
    logger.info(
        f"[explain] Request: word='{original_word}', clean='{clean_input}', lemma='{lemma}', lang='{lang}'"
    )

    # 1. Cache Check
    cached = await service.get_translation(lemma, lang=lang)
    if cached:
        logger.info(f"[explain] Cache HIT for '{lemma}' -> {cached['translation']}")
        return JSONResponse(
            {
                "word": original_word,
                "lemma": lemma,
                "translation": cached["translation"],
                "source": "Cache",
            }
        )

    is_phrase = " " in lemma.strip()

    # 2. Local Dictionary (jamdict) - Skip for phrases
    if lang == "ja" and not is_phrase:
        from ..providers.dictionary_provider import get_dictionary_provider

        logger.info(f"Looking up {lemma} in Jamdict...")
        dict_provider = get_dictionary_provider()

        # Run DB lookup in executor to avoid blocking async loop (SQLite is fast but blocking)
        definition = await loop.run_in_executor(executor, dict_provider.lookup, lemma)

        if definition:
            # Jamdict returns "Kanji (Kana)" or "Kana".
            # Truncate if too long
            translation = definition[:100] + "..." if len(definition) > 100 else definition

            logger.info(f"[explain] Jamdict HIT for '{lemma}' -> {translation}")
            return JSONResponse(
                {
                    "word": original_word,
                    "lemma": lemma,
                    "translation": translation,
                    "source": "Jamdict",
                }
            )

    # 3. Gemini Fallback
    try:
        import os

        from ..features.translate import SUPPORTED_LANGUAGES
        from ..providers import get_ai_provider

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
        provider = get_ai_provider()

        logger.info(f"[explain] Gemini Fallback for '{lemma}' (is_phrase={is_phrase})")

        if is_phrase:
            prompt = f"以下の英文を{lang_name}に翻訳してください。\n\n{original_word}\n\n訳のみを出力してください。"
        else:
            prompt = f"英単語「{lemma}」の{lang_name}訳を1〜3語で簡潔に。訳のみ出力。"

        translate_model = os.getenv("MODEL_TRANSLATE", "gemini-2.0-flash-lite")

        logger.info(f"[explain] Calling AI Provider with model={translate_model}")

        translation = await provider.generate(prompt, model=translate_model)

        service.translation_cache[lemma] = translation
        service.word_cache[lemma] = False

        logger.info(f"[explain] Gemini Success: '{lemma}' -> {translation}")

        return JSONResponse(
            {"word": original_word, "lemma": lemma, "translation": translation, "source": "Gemini"}
        )
    except Exception as e:
        logger.error(f"Gemini translation failed: {e}")
        return JSONResponse(
            {
                "word": original_word,
                "lemma": lemma,
                "translation": "Translation failed",
                "source": "Error",
            }
        )


@router.get("/languages")
async def get_languages():
    return JSONResponse(translation_service.get_supported_languages())


@router.post("/settings/language")
async def set_language(request: LanguageSettingRequest):
    # Store language preference (could be in session or database)
    return JSONResponse({"status": "ok", "language": request.language})


class ExplainContextRequest(BaseModel):
    word: str
    context: str
    session_id: str | None = None
    lang: str = "ja"


@router.post("/explain/context")
async def explain_with_context(req: ExplainContextRequest):
    """Explain word with context using Gemini"""
    import os

    from ..features.translate import SUPPORTED_LANGUAGES
    from ..providers import get_ai_provider

    lang_name = SUPPORTED_LANGUAGES.get(req.lang, req.lang)
    provider = get_ai_provider()

    # Retrieve Paper Summary Context if session_id is provided
    summary_context = ""
    if req.session_id:
        paper_id = storage.get_session_paper_id(req.session_id)
        if paper_id:
            paper = storage.get_paper(paper_id)
            if paper and paper.get("abstract"):
                summary_context = f"\n[Document Summary]\n{paper['abstract']}\n"

    prompt = f"""
以下の文脈において、単語「{req.word}」はどういう意味で使われていますか？
文脈を考慮して、{lang_name}で簡潔に説明してください。

{summary_context}
文脈:
{req.context}
"""
    translate_model = os.getenv("MODEL_TRANSLATE", "gemini-2.0-flash-lite")

    try:
        explanation = await provider.generate(prompt, model=translate_model)
        return JSONResponse(
            {
                "word": req.word,
                "lemma": req.word,
                "translation": explanation,
                "source": "Gemini (Context)",
            }
        )
    except Exception as e:
        logger.error(f"Gemini context explanation failed: {e}")
        return JSONResponse(
            {
                "word": req.word,
                "lemma": req.word,
                "translation": "Explanation failed",
                "source": "Error",
            }
        )
