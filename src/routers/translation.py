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
from ..logic import EnglishAnalysisService, _lookup_word_full, executor

router = APIRouter(tags=["Translation"])

# Services
service = EnglishAnalysisService()
translation_service = TranslationService()


class LanguageSettingRequest(BaseModel):
    session_id: str
    language: str


@router.get("/translate/{word}")
async def translate_word(word: str, lang: str = "ja"):
    result = await translation_service.translate_word(word, lang)
    return JSONResponse(result)


@router.get("/explain/{lemma}")
async def explain(lemma: str, lang: str = "ja"):
    """Word explanation (Cache -> Jamdict -> Gemini)"""

    # 1. Cache Check
    cached = await service.get_translation(lemma, lang=lang)
    if cached:
        return JSONResponse(
            {"word": cached["word"], "translation": cached["translation"], "source": "Cache"}
        )

    # 2. Jamdict (Japanese only)
    if lang == "ja":
        loop = asyncio.get_event_loop()
        lookup_res = await loop.run_in_executor(executor, _lookup_word_full, lemma)

        if lookup_res.entries:
            ja = [
                e.kanji_forms[0].text if e.kanji_forms else e.kana_forms[0].text
                for e in lookup_res.entries[:3]
            ]
            translation = " / ".join(list(dict.fromkeys(ja)))
            return JSONResponse({"word": lemma, "translation": translation, "source": "Jamdict"})

    # 3. Gemini Fallback
    try:
        import os

        from ..features.translate import SUPPORTED_LANGUAGES
        from ..providers import get_ai_provider

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
        provider = get_ai_provider()
        prompt = f"英単語「{lemma}」の{lang_name}訳を1〜3語で簡潔に。訳のみ出力。"
        translate_model = os.getenv("MODEL_TRANSLATE", "gemini-1.5-flash")

        translation = await provider.generate(prompt, model=translate_model)

        service.translation_cache[lemma] = translation
        service.word_cache[lemma] = False

        return JSONResponse({"word": lemma, "translation": translation, "source": "Gemini"})
    except Exception as e:
        logger.error(f"Gemini translation failed: {e}")
        return JSONResponse({"word": lemma, "translation": "Translation failed", "source": "Error"})


@router.get("/languages")
async def get_languages():
    return JSONResponse(translation_service.get_supported_languages())


@router.post("/settings/language")
async def set_language(request: LanguageSettingRequest):
    # Store language preference (could be in session or database)
    return JSONResponse({"status": "ok", "language": request.language})
