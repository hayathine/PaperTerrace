"""
Translation Router
Handles word translation, explanation, and language settings.
"""

import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.domain.features.correspondence_lang_dict import SUPPORTED_LANGUAGES
from app.domain.services.analysis_service import EnglishAnalysisService
from app.providers import get_ai_provider, get_storage_provider
from common.dspy.config import setup_dspy
from common.dspy.modules import (
    DeepExplanationModule,
    SimpleTranslationModule,
    TranslationModule,
)
from common.dspy.trace import TraceContext, trace_dspy_call
from common.logger import ServiceLogger
from common import settings
from common.prompts import (
    CORE_SYSTEM_PROMPT,
)

log = ServiceLogger("Translation")


router = APIRouter(tags=["Translation"])

# Services
service = EnglishAnalysisService()


def build_dict_card_html(
    word: str,
    lemma: str,
    translation: str,
    source: str,
    lang: str = "ja",
    paper_id: str | None = None,
    show_deep_btn: bool = True,
    element_id: str | None = None,
    trace_id: str | None = None,
) -> str:
    """辞書カードのHTMLレイアウトを構築します"""
    paper_param = f"&paper_id={paper_id}" if paper_id else ""
    element_param = f"&element_id={element_id}" if element_id else ""

    # JS safety: escape single quotes for word and lemma, backticks for translation
    js_word = word.replace("'", "\\'").replace('"', '\\"')
    js_translation = translation.replace("`", "\\`").replace("$", "\\$")

    # Copy button
    copy_logic = f"navigator.clipboard.writeText(`{js_translation}`)"
    if trace_id:
        copy_logic += f"; fetch('/api/dspy/trace/{trace_id}/copy', {{method: 'POST'}})"

    copy_btn = f"""
    <button onclick="{copy_logic}; this.innerHTML='COPIED'; setTimeout(()=>this.innerHTML='COPY', 1000)" 
        class="p-1 px-2 text-[8px] font-black text-slate-400 hover:text-indigo-600 bg-slate-50 hover:bg-indigo-50 rounded transition-all uppercase tracking-wider">
        COPY
    </button>
    """

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
            Advanced Translation
        </button>
        """

    # 2. AI Explanation Button (Context Aware)
    # Note: Use js_word for context explanation to keep original word as title
    context_btn = ""
    if element_id:
        context_btn = f"""
        <button 
            onclick="explainWithContext('{element_id}', '{js_word}', '{lang}', '{paper_id or ""}')"
            class="flex-1 py-1.5 flex items-center justify-center gap-1.5 text-[9px] font-bold text-emerald-600 bg-emerald-50 hover:bg-emerald-100 rounded-lg transition-all border border-emerald-100 shadow-sm"
        >
            <svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
            </svg>
            AI解説
        </button>
        """

    # Note saving button: User wants original 'word' as Title, 'translation' as Memo
    save_btn = f"""
    <button onclick="saveWordToNote('{js_word}', `{js_translation}`)" title="Save to Note" 
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
                    {copy_btn}
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
    session_id: str | None = None,
    element_id: str | None = None,
    conf: str | None = None,
    context: str | None = None,
):
    """単語の解説 (Cache -> Gemini)"""
    storage = get_storage_provider()
    start_time = asyncio.get_event_loop().time()
    element_id = element_id or req.headers.get("HX-Trigger")

    log.info(
        "explain", "Word lookup", word=word, element_id=element_id, paper_id=paper_id
    )

    is_htmx = req.headers.get("HX-Request") == "true"

    # 0. Clean input
    clean_input = word.replace("\n", " ").strip(r" .,;!?(){}[\]\"'")
    if not clean_input:
        clean_input = word.strip()

    original_word = word
    lemma = clean_input

    # Calculate user_id (handling guest case)
    current_user_id = getattr(req.state, "user_id", None) or (
        f"guest:{session_id}" if session_id else None
    )

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
        elapsed = asyncio.get_event_loop().time() - start_time
        log.info(
            "explain",
            "Lookup completed (Cache)",
            elapsed=f"{elapsed:.3f}s",
            word=word,
            paper_id=paper_id,
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

    # 2. Gemini Translation
    log.info("explain", "Cache miss, translating with Gemini", lemma=lemma)

    try:
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        # Fetch paper summary context
        paper_context = ""
        if paper_id:
            paper = storage.get_paper(paper_id)
            if paper:
                summary = paper.get("abstract") or paper.get("summary")
                if summary:
                    paper_context = f"\n[Paper Context / Summary]\n{summary}\n"

        if context:
            paper_context += f"\n[Surrounding Context]\n...{context}...\n"

        is_phrase = " " in lemma.strip()
        setup_dspy()
        if is_phrase:
            trans_mod = TranslationModule()
            res, trace_id = await trace_dspy_call(
                "TranslationModule",
                "ContextAwareTranslation",
                trans_mod,
                {
                    "paper_context": paper_context,
                    "target_word": original_word,
                    "user_persona": "Professional Academic Translator",
                    "lang_name": lang_name,
                },
                context=TraceContext(
                    user_id=current_user_id, session_id=session_id, paper_id=paper_id
                ),
            )
            translation = res.translation_and_explanation.strip()
        else:
            simple_mod = SimpleTranslationModule()
            res, trace_id = await trace_dspy_call(
                "SimpleTranslationModule",
                "SimpleTranslation",
                simple_mod,
                {
                    "paper_context": paper_context,
                    "target_word": lemma,
                    "user_persona": "Professional Academic Translator",
                    "lang_name": lang_name,
                },
                context=TraceContext(
                    user_id=current_user_id, session_id=session_id, paper_id=paper_id
                ),
            )
            translation = res.translation.strip()

        service.translation_cache[lemma] = translation
        service.word_cache[lemma] = False

        if not is_htmx:
            return JSONResponse(
                {
                    "word": original_word,
                    "lemma": lemma,
                    "translation": translation,
                    "source": "Gemini",
                    "trace_id": trace_id,
                    "element_id": element_id,
                }
            )

        elapsed = asyncio.get_event_loop().time() - start_time
        log.info(
            "explain",
            "Lookup completed (Gemini)",
            elapsed=f"{elapsed:.3f}s",
            word=word,
            paper_id=paper_id,
        )

        return HTMLResponse(
            build_dict_card_html(
                original_word,
                lemma,
                translation,
                "Gemini AI",
                lang,
                paper_id,
                element_id=element_id,
                trace_id=trace_id,
            )
        )
    except Exception as e:
        log.error(
            "explain", "Gemini fallback translation failed", error=str(e), lemma=lemma
        )

        app_env = settings.get("APP_ENV", "production")
        # 最終的にエラーの場合
        error_msg = (
            f"Translation failed: {str(e)}"
            if app_env == "development"
            else "Translation failed"
        )
        if not is_htmx:
            return JSONResponse(
                {
                    "word": original_word,
                    "lemma": lemma,
                    "translation": error_msg,
                    "source": "Error",
                    "element_id": element_id,
                },
                status_code=500,
            )
        return HTMLResponse(
            build_dict_card_html(
                original_word,
                lemma,
                error_msg,
                "Error",
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
    session_id: str | None = None,
    element_id: str | None = None,
    context: str | None = None,
):
    """Geminiによる詳細翻訳（ユーザー押下により発動）"""
    storage = get_storage_provider()
    # Robust element_id detection
    element_id = element_id or req.headers.get("HX-Trigger")

    is_htmx = req.headers.get("HX-Request") == "true"
    start_time = asyncio.get_event_loop().time()
    # 0. Clean input
    clean_input = word.replace("\n", " ").strip(r" .,;!?(){}[\]\"'")
    if not clean_input:
        clean_input = word.strip()

    original_word = word
    lemma = clean_input  # Initial assumption

    # Calculate user_id (handling guest case)
    current_user_id = getattr(req.state, "user_id", None) or (
        f"guest:{session_id}" if session_id else None
    )

    # Stage 3: Gemini translation
    try:
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)

        # Fetch paper summary context
        paper_context = ""
        if paper_id:
            paper = storage.get_paper(paper_id)
            if paper:
                summary = paper.get("abstract") or paper.get("summary")
                if summary:
                    paper_context = f"\n[Paper Context / Summary]\n{summary}\n"

        if context:
            paper_context += f"\n[Surrounding Context]\n...{context}...\n"

        log.info("explain_deep", "Gemini call", lemma=lemma)

        # DSPy version
        setup_dspy()
        trans_mod = TranslationModule()
        # Single words might need different prompt, but for now use context aware phrase translation
        res, trace_id = await trace_dspy_call(
            "TranslationModule",
            "ContextAwareTranslation",
            trans_mod,
            {
                "paper_context": paper_context,
                "target_word": original_word,
                "user_persona": "Professional Academic Translator",
                "lang_name": lang_name,
            },
            context=TraceContext(
                user_id=current_user_id, session_id=session_id, paper_id=paper_id
            ),
        )
        translation = res.translation_and_explanation.strip()

        service.translation_cache[lemma] = translation
        service.word_cache[lemma] = False

        if not is_htmx:
            return JSONResponse(
                {
                    "word": original_word,
                    "lemma": lemma,
                    "translation": translation,
                    "source": "Gemini",
                    "trace_id": trace_id,
                    "element_id": element_id,
                }
            )

        elapsed = asyncio.get_event_loop().time() - start_time
        log.info(
            "explain_deep",
            "Deep lookup completed",
            elapsed=f"{elapsed:.3f}s",
            word=word,
            paper_id=paper_id,
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
                trace_id=trace_id,
            )
        )
    except Exception as e:
        log.error(
            "explain_deep", "Gemini translation failed", error=str(e), lemma=lemma
        )
        from app.core.config import is_production

        error_msg = (
            str(e) if not is_production() else "An error occurred during translation."
        )
        if not is_htmx:
            return JSONResponse(
                {
                    "word": original_word,
                    "lemma": lemma,
                    "translation": error_msg,
                    "source": "Error",
                    "element_id": element_id,
                },
                status_code=500,
            )
        return HTMLResponse(
            build_dict_card_html(
                original_word,
                lemma,
                error_msg,
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
async def explain_with_context(req: ExplainContextRequest, request: Request):
    """Explain word with context using Gemini"""
    storage = get_storage_provider()
    start_time = asyncio.get_event_loop().time()
    lang_name = SUPPORTED_LANGUAGES.get(req.lang, req.lang)

    # Retrieve Paper Summary Context if session_id is provided
    summary_context = ""
    paper_id = None
    if req.session_id:
        paper_id = storage.get_session_paper_id(req.session_id)
        if paper_id:
            paper = storage.get_paper(paper_id)
            if paper and paper.get("abstract"):
                summary_context = f"\n[Document Summary]\n{paper['abstract']}\n"

    try:
        # DSPy version
        setup_dspy()
        # DeepExplanation uses summary_context, context, word, lang_name
        deep_mod = DeepExplanationModule()
        res, trace_id = await trace_dspy_call(
            "DeepExplanationModule",
            "DeepExplanation",
            deep_mod,
            {
                "summary_context": summary_context,
                "context": req.context,
                "target_word": req.word,
                "user_persona": "Academic Expert",
                "lang_name": lang_name,
            },
            context=TraceContext(
                user_id=(
                    getattr(request.state, "user_id", None)
                    or (f"guest:{req.session_id}" if req.session_id else None)
                ),
                session_id=req.session_id,
                paper_id=paper_id,
            ),
        )
        explanation = res.explanation

        elapsed = asyncio.get_event_loop().time() - start_time
        log.info(
            "explain_context",
            "Context lookup completed",
            elapsed=f"{elapsed:.3f}s",
            word=req.word,
            paper_id=paper_id,
        )

        return JSONResponse(
            {
                "word": req.word,
                "lemma": req.word,
                "translation": explanation,
                "source": "Gemini (Context)",
                "trace_id": trace_id,
            }
        )
    except Exception as e:
        log.error(
            "explain_context",
            "Gemini context explanation failed",
            error=str(e),
            word=req.word,
        )
        return JSONResponse(
            {
                "word": req.word,
                "lemma": req.word,
                "translation": "Explanation failed",
                "source": "Error",
            }
        )


class ExplainImageRequest(BaseModel):
    image_url: str
    prompt: str
    session_id: str | None = None
    paper_id: str | None = None
    lang: str = "ja"


@router.post("/explain/image")
async def explain_image(req: ExplainImageRequest, request: Request):
    """Explain image with context using Gemini"""
    start_time = asyncio.get_event_loop().time()
    lang_name = SUPPORTED_LANGUAGES.get(req.lang, req.lang)
    provider = get_ai_provider()

    from app.providers import get_image_bytes

    try:
        # GCSダウンロードは同期ブロッキングI/Oのため、イベントループをブロックしないようexecutorで実行
        loop = asyncio.get_event_loop()
        image_bytes = await loop.run_in_executor(
            None, lambda: get_image_bytes(req.image_url)
        )
    except Exception as e:
        log.error(
            "explain_image",
            "Failed to get image bytes",
            image_url=req.image_url,
            error=str(e),
        )

        return JSONResponse(
            {
                "word": req.prompt,
                "lemma": req.prompt,
                "translation": "画像の読み込みに失敗しました。",
                "source": "Error",
            },
            status_code=500,
        )

    # Retrieve Paper Summary Context if paper_id is provided
    # ... Optional but left for future structure

    model = settings.get("MODEL_TRANSLATE", "gemini-2.5-flash-lite")
    prompt = f"[{lang_name}で回答してください]\n{req.prompt}"

    url_lower = req.image_url.lower()
    if url_lower.endswith(".jpg") or url_lower.endswith(".jpeg"):
        img_mime_type = "image/jpeg"
    elif url_lower.endswith(".webp"):
        img_mime_type = "image/webp"
    else:
        img_mime_type = "image/jpeg"

    try:
        explanation = await provider.generate_with_image(
            prompt=prompt,
            image_bytes=image_bytes,
            mime_type=img_mime_type,
            model=model,
            system_instruction=CORE_SYSTEM_PROMPT,
        )
        elapsed = asyncio.get_event_loop().time() - start_time
        current_user_id = getattr(request.state, "user_id", None) or (
            f"guest:{req.session_id}" if req.session_id else None
        )
        log.info(
            "explain_image",
            "Image explanation completed",
            elapsed=f"{elapsed:.3f}s",
            word=req.prompt,
            paper_id=req.paper_id,
            user_id=current_user_id,
            session_id=req.session_id,
        )

        return JSONResponse(
            {
                "word": req.prompt,
                "lemma": req.prompt,
                "translation": explanation,
                "source": "Gemini (Image)",
            }
        )
    except Exception as e:
        log.error(
            "explain_image",
            "Gemini image explanation failed",
            error=str(e),
            prompt=req.prompt,
        )
        return JSONResponse(
            {
                "word": req.prompt,
                "lemma": req.prompt,
                "translation": "画像の解説に失敗しました。",
                "source": "Error",
            },
            status_code=500,
        )
