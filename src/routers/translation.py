"""
Translation Router
Handles word translation, explanation, and language settings.
"""

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

import google.genai as genai
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from ..feature import TranslationService
from ..logger import logger
from ..logic import EnglishAnalysisService, _lookup_word_full

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
    bg_class = "bg-blue-50" if result["source"] == "cache" else "bg-purple-50"
    return HTMLResponse(
        f'<div class="p-4 rounded-lg {bg_class} border animate-fade-in">'
        f"<b>{result['word']}</b>"
        f"<p>{result['translation']}</p>"
        f"<small class='text-slate-400'>{result['target_lang']}</small>"
        f"</div>"
    )


@router.get("/explain/{lemma}")
async def explain(lemma: str):
    """単語の説明を取得（キャッシュ → Jamdict → Gemini の順で検索）"""
    # まずキャッシュから翻訳を取得
    cached = service.get_translation(lemma)
    if cached:
        bg = "bg-purple-50"
        return HTMLResponse(
            f'<div class="p-4 rounded-lg {bg} border animate-fade-in"><b>{cached["word"]}</b>'
            f"<p>{cached['translation']}</p>"
            f'<small class="text-slate-400">{cached["source"]}</small></div>'
        )

    # キャッシュにない場合は Jamdict を検索
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=2)
    lookup_res = await loop.run_in_executor(executor, _lookup_word_full, lemma)

    if lookup_res.entries:
        ja = [
            e.kanji_forms[0].text if e.kanji_forms else e.kana_forms[0].text
            for e in lookup_res.entries[:3]
        ]
        translation = " / ".join(list(dict.fromkeys(ja)))
        return HTMLResponse(
            f'<div class="p-4 rounded-lg bg-blue-50 border animate-fade-in"><b>{lemma}</b>'
            f"<p>{translation}</p>"
            f'<small class="text-slate-400">Jamdict</small></div>'
        )

    # Jamdict にもない場合は Gemini で個別翻訳
    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        model = os.getenv("OCR_MODEL") or "gemini-1.5-flash"
        prompt = f"英単語「{lemma}」の日本語訳を1〜3語で簡潔に。訳のみ出力。"

        res = client.models.generate_content(model=model, contents=prompt)
        translation = res.text.strip() if res.text else "翻訳できませんでした"

        # キャッシュに保存（次回以降は高速に）
        service.translation_cache[lemma] = translation
        service.word_cache[lemma] = False  # Jamdictにはない

        return HTMLResponse(
            f'<div class="p-4 rounded-lg bg-amber-50 border animate-fade-in"><b>{lemma}</b>'
            f"<p>{translation}</p>"
            f'<small class="text-slate-400">Gemini</small></div>'
        )
    except Exception as e:
        logger.error(f"Gemini translation failed for '{lemma}': {e}")
        return HTMLResponse(
            f'<div class="p-4 rounded-lg bg-gray-50 border animate-fade-in"><b>{lemma}</b>'
            f"<p>翻訳に失敗しました</p>"
            f'<small class="text-slate-400">Error</small></div>'
        )


@router.get("/languages")
async def get_languages():
    return JSONResponse(translation_service.get_supported_languages())


@router.post("/settings/language")
async def set_language(request: LanguageSettingRequest):
    # Store language preference (could be in session or database)
    return JSONResponse({"status": "ok", "language": request.language})
