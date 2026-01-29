"""
Translation Router
Handles word translation, explanation, and language settings.
"""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
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


def build_dict_card_html(
    word: str,
    lemma: str,
    translation: str,
    source: str,
    lang: str = "ja",
    paper_id: str | None = None,
    show_deep_btn: bool = True,
    element_id: str | None = None,
) -> str:
    """辞書カードのHTMLレイアウトを構築します"""
    paper_param = f"&paper_id={paper_id}" if paper_id else ""
    deep_btn = ""
    if show_deep_btn:
        deep_btn = f"""
        <button 
            hx-get="/explain-deep/{lemma}?lang={lang}{paper_param}"
            hx-target="closest .dict-card"
            hx-swap="outerHTML"
            hx-indicator="#dict-loading"
            class="mt-3 w-full py-2 flex items-center justify-center gap-2 text-[10px] font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-xl transition-all border border-indigo-100 shadow-sm"
        >
            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            AIで再翻訳 (Gemini)
        </button>
        """

    # Note saving button
    save_btn = f"""
    <button onclick="saveWordToNote('{lemma}', '{translation}')" title="Save to Note" 
        class="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-indigo-50 rounded-lg transition-all">
        <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" />
        </svg>
    </button>
    """

    source_label = f"""<span class="px-1.5 py-0.5 bg-slate-100 text-slate-400 rounded text-[8px] font-bold uppercase tracking-wider">{source}</span>"""

    jump_btn = ""
    if element_id:
        jump_btn = f"""
        <button onclick="jumpToElement('{element_id}')" title="Jump to word" 
            class="p-1.5 text-slate-400 hover:text-indigo-600 hover:bg-slate-50 rounded-lg transition-all">
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
        </button>
        """

    return f"""
    <div class="dict-card p-4 bg-white border border-slate-100 rounded-2xl shadow-sm animate-fade-in group hover:shadow-md transition-all">
        <div class="flex items-start justify-between mb-3">
            <div class="flex flex-col">
                <div class="flex items-center gap-2 mb-0.5">
                    <span class="text-xs font-black text-slate-800 tracking-tight">{word}</span>
                    {source_label}
                </div>
                <span class="text-[9px] font-bold text-slate-400 font-mono italic">lemma: {lemma}</span>
            </div>
            <div class="flex items-center gap-1">
                {jump_btn}
                {save_btn}
                <button onclick="this.closest('.dict-card').remove()" class="p-1.5 text-slate-300 hover:text-slate-500 transition-colors text-sm">×</button>
            </div>
        </div>
        <div class="text-xs font-semibold text-indigo-600 leading-relaxed bg-indigo-50/30 p-3 rounded-xl border border-indigo-50/50">
            {translation}
        </div>
        {deep_btn}
    </div>
    """


@router.get("/explain/{word}")
async def explain(
    req: Request,
    word: str,
    lang: str = "ja",
    paper_id: str | None = None,
    element_id: str | None = None,
):
    """単語の解説 (Local: Cache -> Jamdict -> local-MT)"""
    loop = asyncio.get_event_loop()
    is_htmx = req.headers.get("HX-Request") == "true"

    # 0. Lemmatize input
    clean_input = word.replace("\n", " ").strip(" .,;!?(){}[\]\"'")
    if not clean_input:
        clean_input = word.strip()

    lemma = await loop.run_in_executor(executor, service.lemmatize, clean_input)
    original_word = word

    # 1. Cache Check
    cached = await service.get_translation(lemma, lang=lang)
    if cached:
        if not is_htmx:
            return JSONResponse(
                {
                    "word": original_word,
                    "lemma": lemma,
                    "translation": cached["translation"],
                    "source": "Cache",
                    "element_id": element_id,
                }
            )
        return HTMLResponse(
            build_dict_card_html(
                original_word,
                lemma,
                cached["translation"],
                "Cache",
                lang,
                paper_id,
                element_id=element_id,
            )
        )

    is_phrase = " " in lemma.strip()

    # Stage 1: Local Dictionary (Jamdict)
    if lang == "ja" and not is_phrase:
        from ..providers.dictionary_provider import get_dictionary_provider

        dict_provider = get_dictionary_provider()
        definition = await loop.run_in_executor(executor, dict_provider.lookup, lemma)
        if definition:
            translation = definition[:100] + "..." if len(definition) > 100 else definition
            if not is_htmx:
                return JSONResponse(
                    {
                        "word": original_word,
                        "lemma": lemma,
                        "translation": translation,
                        "source": "Jamdict",
                    }
                )
            return HTMLResponse(
                build_dict_card_html(
                    original_word,
                    lemma,
                    translation,
                    "Jamdict",
                    lang,
                    paper_id,
                    element_id=element_id,
                )
            )

    # Stage 2: Local Machine Translation (M2M100)
    if lang == "ja":
        from ..services.local_translator import get_local_translator

        local_translator = get_local_translator()
        local_translation = await loop.run_in_executor(executor, local_translator.translate, lemma)
        if local_translation:
            service.translation_cache[lemma] = local_translation
            service.word_cache[lemma] = False
            if not is_htmx:
                return JSONResponse(
                    {
                        "word": original_word,
                        "lemma": lemma,
                        "translation": local_translation,
                        "source": "Local-MT",
                    }
                )
            return HTMLResponse(
                build_dict_card_html(
                    original_word,
                    lemma,
                    local_translation,
                    "Local-MT",
                    lang,
                    paper_id,
                    element_id=element_id,
                )
            )

    # 見つからない場合もローカル翻訳の枠組みで「未発見」として返し、AIボタンを表示
    if not is_htmx:
        return JSONResponse(
            {
                "word": original_word,
                "lemma": lemma,
                "translation": "Not found in local dict",
                "source": "Search",
                "element_id": element_id,
            }
        )
    return HTMLResponse(
        build_dict_card_html(
            original_word,
            lemma,
            "Not found in local dict",
            "Search",
            lang,
            paper_id,
            element_id=element_id,
        )
    )


@router.get("/explain-deep/{word}")
async def explain_deep(
    req: Request,
    word: str,
    lang: str = "ja",
    paper_id: str | None = None,
    element_id: str | None = None,
):
    """Geminiによる詳細翻訳（ユーザー押下により発動）"""
    is_htmx = req.headers.get("HX-Request") == "true"
    # 0. Lemmatize input
    clean_input = word.replace("\n", " ").strip(" .,;!?(){}[\]\"'")
    if not clean_input:
        clean_input = word.strip()

    lemma = await asyncio.get_event_loop().run_in_executor(executor, service.lemmatize, clean_input)
    original_word = word

    # Stage 3: Gemini translation
    try:
        import os

        from ..features.translate import SUPPORTED_LANGUAGES
        from ..providers import get_ai_provider

        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
        provider = get_ai_provider()

        # Fetch paper summary context
        paper_context = ""
        if paper_id:
            paper = storage.get_paper(paper_id)
            if paper:
                summary = paper.get("abstract") or paper.get("summary")
                if summary:
                    paper_context = f"\n[Paper Context / Summary]\n{summary}\n"

        logger.info(f"[explain-deep] Gemini Call for '{lemma}'")

        is_phrase = " " in lemma.strip()
        if is_phrase:
            prompt = f"{paper_context}\n以上の文脈を考慮して、以下の英文を{lang_name}に翻訳してください。\n\n{original_word}\n\n訳のみを出力してください。"
        else:
            prompt = f"{paper_context}\n以上の論文の文脈において、英単語「{lemma}」はどのような意味ですか？\n{lang_name}訳を1〜3語で簡潔に。訳のみ出力。"

        translate_model = os.getenv("MODEL_TRANSLATE", "gemini-2.0-flash-lite")
        translation = (await provider.generate(prompt, model=translate_model)).strip().strip("'\"")

        service.translation_cache[lemma] = translation
        service.word_cache[lemma] = False

        if not is_htmx:
            return JSONResponse(
                {
                    "word": original_word,
                    "lemma": lemma,
                    "translation": translation,
                    "source": "Gemini",
                    "element_id": element_id,
                }
            )

        return HTMLResponse(
            build_dict_card_html(
                original_word,
                lemma,
                translation,
                "Gemini AI",
                lang,
                paper_id,
                show_deep_btn=False,
                element_id=element_id,
            )
        )
    except Exception as e:
        logger.error(f"Gemini translation failed: {e}")
        if not is_htmx:
            return JSONResponse(
                {
                    "word": original_word,
                    "lemma": lemma,
                    "translation": "Translation failed",
                    "source": "Error",
                    "element_id": element_id,
                },
                status_code=500,
            )
        return HTMLResponse(
            build_dict_card_html(
                original_word,
                lemma,
                "Translation failed",
                "Error",
                lang,
                paper_id,
                element_id=element_id,
            )
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
