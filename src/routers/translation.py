"""
Translation Router
Handles word translation, explanation, and language settings.
"""

import asyncio

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, JSONResponse
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
    bg_class = "bg-blue-50" if result["source"] == "cache" else "bg-purple-50"
    return HTMLResponse(
        f'<div class="p-4 rounded-lg {bg_class} border animate-fade-in">'
        f"<b>{result['word']}</b>"
        f"<p>{result['translation']}</p>"
        f"<small class='text-slate-400'>{result['target_lang']}</small>"
        f"</div>"
    )


@router.get("/explain/{lemma}")
async def explain(lemma: str, lang: str = "ja"):
    """単語の説明を取得（キャッシュ → Jamdict → Gemini の順で検索）"""

    def make_card(
        word: str, translation: str, source: str, bg_class: str, border_class: str
    ) -> str:
        """辞書カードHTMLを生成"""
        source_colors = {
            "Cache": "bg-purple-100 text-purple-600",
            "Jamdict": "bg-blue-100 text-blue-600",
            "Gemini": "bg-amber-100 text-amber-600",
            "Error": "bg-gray-100 text-gray-600",
        }
        source_style = source_colors.get(source, "bg-gray-100 text-gray-600")
        # 脱出処理を追加（シングルクォートなど）
        safe_word = word.replace("'", "\\'")
        safe_trans = translation.replace("'", "\\'").replace("\n", " ")

        return f"""<div class="dict-card p-4 {bg_class} border {border_class} rounded-xl shadow-sm animate-fade-in group hover:shadow-md transition-all">
            <div class="flex items-start justify-between gap-2 mb-2">
                <span class="text-sm font-bold text-slate-700">{word}</span>
                <div class="flex items-center gap-1.5">
                    <button onclick="saveWordToNote('{safe_word}', '{safe_trans}')" title="Save to Note" class="p-1 text-slate-400 hover:text-indigo-600 hover:bg-white rounded transition-all opacity-0 group-hover:opacity-100">
                        <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg>
                    </button>
                    <span class="text-[9px] font-medium px-2 py-0.5 rounded-full {source_style}">{source}</span>
                </div>
            </div>
            <p class="text-sm text-slate-600 leading-relaxed">{translation}</p>
        </div>
        <script>document.getElementById('dict-empty-state')?.remove();</script>"""

    # まずキャッシュから翻訳を取得
    cached = await service.get_translation(lemma, lang=lang)
    if cached:
        return HTMLResponse(
            make_card(
                cached["word"],
                cached["translation"],
                "Cache",
                "bg-purple-50/80",
                "border-purple-100",
            )
        )

    # キャッシュにない場合は Jamdict を検索 (日本語の場合のみ)
    if lang == "ja":
        loop = asyncio.get_event_loop()
        # executor は src.logic からインポートしたものを使用（スレッド/DB接続の再利用のため）
        lookup_res = await loop.run_in_executor(executor, _lookup_word_full, lemma)

        if lookup_res.entries:
            ja = [
                e.kanji_forms[0].text if e.kanji_forms else e.kana_forms[0].text
                for e in lookup_res.entries[:3]
            ]
            translation = " / ".join(list(dict.fromkeys(ja)))
            return HTMLResponse(
                make_card(lemma, translation, "Jamdict", "bg-blue-50/80", "border-blue-100")
            )

    # Jamdict にもない（または日本語以外）場合は Gemini で個別翻訳
    try:
        import os

        from ..features.translate import SUPPORTED_LANGUAGES
        from ..providers import get_ai_provider

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        provider = get_ai_provider()
        prompt = f"英単語「{lemma}」の{lang_name}訳を1〜3語で簡潔に。訳のみ出力。"
        translate_model = os.getenv("MODEL_TRANSLATE", "gemini-1.5-flash")

        translation = await provider.generate(prompt, model=translate_model)

        # キャッシュに保存（次回以降は高速に）
        service.translation_cache[lemma] = translation
        service.word_cache[lemma] = False  # Jamdictにはない

        return HTMLResponse(
            make_card(lemma, translation, "Gemini", "bg-amber-50/80", "border-amber-100")
        )
    except Exception as e:
        logger.error(f"Gemini translation failed for '{lemma}': {e}")
        return HTMLResponse(
            make_card(lemma, "翻訳に失敗しました", "Error", "bg-gray-50/80", "border-gray-200")
        )


@router.get("/languages")
async def get_languages():
    return JSONResponse(translation_service.get_supported_languages())


@router.post("/settings/language")
async def set_language(request: LanguageSettingRequest):
    # Store language preference (could be in session or database)
    return JSONResponse({"status": "ok", "language": request.language})
