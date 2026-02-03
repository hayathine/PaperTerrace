"""
Translation Router
Handles word translation, explanation, and language settings.
"""

import asyncio
import os

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from src.domain.features.translate import SUPPORTED_LANGUAGES
from src.domain.prompts import (
    CORE_SYSTEM_PROMPT,
    DICT_EXPLAIN_WORD_CONTEXT_PROMPT,
    DICT_TRANSLATE_PHRASE_CONTEXT_PROMPT,
    DICT_TRANSLATE_WORD_SIMPLE_PROMPT,
)
from src.domain.services import local_translator
from src.domain.services.analysis_service import EnglishAnalysisService
from src.logger import get_service_logger
from src.logic import executor
from src.providers import get_ai_provider, get_storage_provider

log = get_service_logger("Translation")

router = APIRouter(tags=["Translation"])

# Services
service = EnglishAnalysisService()
storage = get_storage_provider()


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
    element_param = f"&element_id={element_id}" if element_id else ""

    # 1. AI Re-translate Button (Lemma based)
    deep_btn = ""
    if show_deep_btn:
        deep_btn = f"""
        <button 
            hx-get="/explain-deep/{lemma}?lang={lang}{paper_param}{element_param}"
            hx-target="closest .dict-card"
            hx-swap="outerHTML"
            hx-indicator="#dict-loading"
            class="flex-1 py-1.5 flex items-center justify-center gap-1.5 text-[9px] font-bold text-indigo-600 bg-indigo-50 hover:bg-indigo-100 rounded-lg transition-all border border-indigo-100 shadow-sm"
        >
            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            AI再翻訳
        </button>
        """

    # 2. AI Explanation Button (Context Aware)
    context_btn = ""
    if element_id:
        context_btn = f"""
        <button 
            onclick="explainWithContext('{element_id}', '{lemma}', '{lang}', '{paper_id or ""}')"
            class="flex-1 py-1.5 flex items-center justify-center gap-1.5 text-[9px] font-bold text-emerald-600 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-all border border-emerald-100 shadow-sm"
        >
            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            AI解説
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
            class="flex-1 py-1.5 flex items-center justify-center gap-1.5 text-[9px] font-bold text-slate-600 bg-slate-50 hover:bg-slate-100 rounded-lg transition-all border border-slate-200 shadow-sm"
        >
            <svg class="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
            </svg>
            該当箇所へ
        </button>
        """

    actions_row = ""
    if deep_btn or context_btn or jump_btn:
        actions_row = f"""
        <div class="flex flex-wrap gap-2 mt-3">
            {jump_btn}
            {deep_btn}
            {context_btn}
        </div>
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
                {save_btn}
                <button onclick="this.closest('.dict-card').remove()" class="p-1.5 text-slate-300 hover:text-slate-500 transition-colors text-sm">×</button>
            </div>
        </div>
        <div class="text-xs font-semibold text-indigo-600 leading-relaxed bg-indigo-50/30 p-3 rounded-xl border border-indigo-50/50">
            {translation}
        </div>
        {actions_row}
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
    """単語の解説 (Local: Cache -> local-MT)"""
    # Robust element_id detection: Try query param, then fallback to HTMX header
    element_id = element_id or req.headers.get("HX-Trigger")

    log.debug("explain", f"Word lookup: {word}", element_id=element_id)

    loop = asyncio.get_event_loop()
    is_htmx = req.headers.get("HX-Request") == "true"

    # 0. Lemmatize input
    clean_input = word.replace("\n", " ").strip(r" .,;!?(){}[\]\"'")
    if not clean_input:
        clean_input = word.strip()

    lemma = await loop.run_in_executor(executor, service.lemmatize, clean_input)
    original_word = word

    # 1. Cache Check
    cached = await service.get_translation(lemma, lang=lang)
    if cached:
        source = cached.get("source", "Cache")
        if not is_htmx:
            return JSONResponse(
                {
                    "word": original_word,
                    "lemma": lemma,
                    "translation": cached["translation"],
                    "source": source,
                    "element_id": element_id,
                }
            )
        return HTMLResponse(
            build_dict_card_html(
                original_word,
                lemma,
                cached["translation"],
                source,
                lang,
                paper_id,
                element_id=element_id,
            )
        )

    # Stage 2: Local Machine Translation (M2M100)
    local_translation = await loop.run_in_executor(
        executor, local_translator.get_local_translator, lemma
    )
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
    # Robust element_id detection
    element_id = element_id or req.headers.get("HX-Trigger")

    is_htmx = req.headers.get("HX-Request") == "true"
    # 0. Lemmatize input
    clean_input = word.replace("\n", " ").strip(r" .,;!?(){}[\]\"'")
    if not clean_input:
        clean_input = word.strip()

    lemma = await asyncio.get_event_loop().run_in_executor(executor, service.lemmatize, clean_input)
    original_word = word

    # Stage 3: Gemini translation
    try:
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

        log.info("explain_deep", "Gemini call", lemma=lemma)

        is_phrase = " " in lemma.strip()
        if is_phrase:
            prompt = DICT_TRANSLATE_PHRASE_CONTEXT_PROMPT.format(
                paper_context=paper_context, lang_name=lang_name, original_word=original_word
            )
        else:
            prompt = DICT_TRANSLATE_WORD_SIMPLE_PROMPT.format(
                paper_context=paper_context, lemma=lemma, lang_name=lang_name
            )

        translate_model = os.getenv("MODEL_TRANSLATE", "gemini-2.5-flash-lite")
        translation = (
            (
                await provider.generate(
                    prompt, model=translate_model, system_instruction=CORE_SYSTEM_PROMPT
                )
            )
            .strip()
            .strip("'\"")
        )

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
        log.error("explain_deep", "Gemini translation failed", error=str(e))
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


class ExplainContextRequest(BaseModel):
    word: str
    context: str
    session_id: str | None = None
    lang: str = "ja"


@router.post("/explain/context")
async def explain_with_context(req: ExplainContextRequest):
    """Explain word with context using Gemini"""
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

    prompt = DICT_EXPLAIN_WORD_CONTEXT_PROMPT.format(
        word=req.word, lang_name=lang_name, summary_context=summary_context, context=req.context
    )
    translate_model = os.getenv("MODEL_TRANSLATE", "gemini-2.5-flash-lite")

    try:
        explanation = await provider.generate(
            prompt, model=translate_model, system_instruction=CORE_SYSTEM_PROMPT
        )
        return JSONResponse(
            {
                "word": req.word,
                "lemma": req.word,
                "translation": explanation,
                "source": "Gemini (Context)",
            }
        )
    except Exception as e:
        log.error("explain_context", "Gemini context explanation failed", error=str(e))
        return JSONResponse(
            {
                "word": req.word,
                "lemma": req.word,
                "translation": "Explanation failed",
                "source": "Error",
            }
        )
