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
from ..services.jamdict_service import _lookup_word_full

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
    # 0. Assume input word is already lemmatized by frontend
    lemma = word.lower().strip(".,;!?(){}[\]\"'")
    original_word = word  # Input is typically lemma from frontend
    loop = asyncio.get_event_loop()

    # logger.info(f"[explain] word='{word}' -> lemma='{lemma}'")

    # 1. Cache Check
    cached = await service.get_translation(lemma, lang=lang)
    if cached:
        return JSONResponse(
            {
                "word": original_word,
                "lemma": lemma,
                "translation": cached["translation"],
                "source": "Cache",
            }
        )

    # 2. Jamdict (Japanese only)
    if lang == "ja":
        lookup_res = await loop.run_in_executor(executor, _lookup_word_full, lemma)

        if lookup_res.entries:
            ja = [
                e.kanji_forms[0].text if e.kanji_forms else e.kana_forms[0].text
                for e in lookup_res.entries[:3]
            ]
            translation = " / ".join(list(dict.fromkeys(ja)))
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
        prompt = f"英単語「{lemma}」の{lang_name}訳を1〜3語で簡潔に。訳のみ出力。"
        translate_model = os.getenv("MODEL_TRANSLATE", "gemini-2.0-flash-lite")

        translation = await provider.generate(prompt, model=translate_model)

        service.translation_cache[lemma] = translation
        service.word_cache[lemma] = False

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
