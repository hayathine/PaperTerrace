"""
Translation Router
Handles word translation, explanation, and language settings.
"""

import asyncio
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, Field, field_validator

from app.database import get_orm_storage
from app.domain.features.correspondence_lang_dict import SUPPORTED_LANGUAGES
from app.domain.services.analysis_service import EnglishAnalysisService
from app.providers import get_ai_provider
from app.providers.orm_storage import ORMStorageAdapter
from common.dspy_utils.modules import (
    SentenceTranslationModule,
    SimpleTranslationModule,
    TranslationModule,
)
from common.dspy_utils.trace import TraceContext, trace_dspy_call
from common.logger import ServiceLogger
from app.core.config import is_local
from common import settings
from common.dspy_seed_prompt import (
    CORE_SYSTEM_PROMPT,
    EXPLAIN_FROM_PDF_PROMPT,
    SENTENCE_TRANSLATE_FROM_PDF_PROMPT,
    TRANSLATE_FROM_PDF_PROMPT,
)
from redis_provider.provider import RedisService
from app.domain.features.cache_utils import get_pdf_cache_key

log = ServiceLogger("Translation")


router = APIRouter(tags=["Translation"])

# Services
service = EnglishAnalysisService()
redis_service = RedisService()


# ---------------------------------------------------------------------------
# 共通ヘルパー関数
# ---------------------------------------------------------------------------

def _clean_word(word: str) -> str:
    """入力テキストから改行・前後の句読点を除去する。空になった場合は元の文字列を返す。"""
    cleaned = word.replace("\n", " ").strip(r" .,;!?(){}[\]\"'")
    return cleaned if cleaned else word.strip()


def _get_pdf_cache_name(paper_id: str | None) -> str | None:
    """論文の PDF コンテキストキャッシュ名を Redis から取得する。なければ None。"""
    if not paper_id:
        return None
    return redis_service.get(get_pdf_cache_key(paper_id))


async def _generate_with_pdf_cache(
    word: str,
    context: str | None,
    prompt_template: str,
    lang_name: str,
    pdf_cache_name: str,
) -> str:
    """PDF コンテキストキャッシュを使って AI による翻訳・解説テキストを生成する。

    Args:
        word: 対象の単語またはフレーズ。
        context: 周辺テキスト（省略可）。
        prompt_template: `target_word`・`context_line`・`lang_name` を含むプロンプトテンプレート。
        lang_name: 翻訳先の言語名。
        pdf_cache_name: Gemini のコンテキストキャッシュ名。

    Returns:
        生成された翻訳・解説テキスト。
    """
    context_line = f"\nSurrounding context: ...{context}...\n" if context else ""
    prompt = prompt_template.format(
        target_word=word,
        context_line=context_line,
        lang_name=lang_name,
    )
    ai_provider = get_ai_provider()
    raw = await ai_provider.generate(
        prompt=prompt,
        model=settings.get("MODEL_TRANSLATE", "gemini-2.5-flash-lite"),
        cached_content_name=pdf_cache_name,
    )
    return (str(raw) if raw else "").strip()


def _resolve_user_id(request: Request, session_id: str | None) -> str | None:
    """リクエストから user_id を解決する。ゲストの場合は session_id を利用。"""
    return getattr(request.state, "user_id", None) or (
        f"guest:{session_id}" if session_id else None
    )


def _build_paper_context(
    paper_id: str | None,
    context: str | None,
    storage: "ORMStorageAdapter",
) -> str:
    """paper_id から論文サマリを取得し、周辺テキストと結合してコンテキスト文字列を構築する。"""
    paper_context = ""
    if paper_id:
        paper = storage.get_paper(paper_id)
        if paper:
            summary = paper.get("abstract") or paper.get("summary")
            if summary:
                paper_context = f"\n[Paper Context / Summary]\n{summary}\n"
    if context:
        paper_context += f"\n[Surrounding Context]\n...{context}...\n"
    return paper_context


def _make_response(
    word: str,
    lemma: str,
    translation: str,
    source: str,
    is_htmx: bool,
    element_id: str | None = None,
    trace_id: str | None = None,
    lang: str = "ja",
    paper_id: str | None = None,
    paper_title: str | None = None,
    show_deep_btn: bool = True,
    status_code: int = 200,
    html_source: str | None = None,
):
    """is_htmx に応じて JSONResponse または HTMLResponse を返す共通ヘルパー。
    html_source を指定すると、HTML レスポンスのソース表示ラベルを上書きできる。
    """
    if not is_htmx:
        return JSONResponse(
            {
                "word": word,
                "lemma": lemma,
                "translation": translation,
                "source": source,
                "trace_id": trace_id,
                "element_id": element_id,
            },
            status_code=status_code,
        )
    return HTMLResponse(
        build_dict_card_html(
            DictCardData(
                word=word,
                lemma=lemma,
                translation=translation,
                source=html_source or source,
                lang=lang,
                paper_id=paper_id,
                paper_title=paper_title,
                show_deep_btn=show_deep_btn,
                element_id=element_id,
                trace_id=trace_id,
            )
        )
    )


@dataclass
class DictCardData:
    """辞書カード描画に必要なデータを保持するデータクラス。"""

    word: str
    lemma: str
    translation: str
    source: str
    lang: str = "ja"
    paper_id: str | None = None
    paper_title: str | None = None
    show_deep_btn: bool = True
    element_id: str | None = None
    trace_id: str | None = None


def build_dict_card_html(data: DictCardData) -> str:
    """辞書カードのHTMLレイアウトを構築します"""
    word = data.word
    lemma = data.lemma
    translation = data.translation
    source = data.source
    lang = data.lang
    paper_id = data.paper_id
    paper_title = data.paper_title
    show_deep_btn = data.show_deep_btn
    element_id = data.element_id
    trace_id = data.trace_id
    import html as _html

    paper_param = f"&paper_id={paper_id}" if paper_id else ""
    element_param = f"&element_id={element_id}" if element_id else ""
    title_param = f"&paper_title={_html.escape(paper_title)}" if paper_title else ""

    # HTML attribute context: HTML-encode to prevent attribute injection
    # These values appear inside HTML attribute strings (onclick="..."), so
    # HTML-encoding (& → &amp;, " → &quot;, etc.) is the correct defense.
    attr_word = _html.escape(word, quote=True)
    attr_element_id = _html.escape(element_id, quote=True) if element_id else ""
    attr_paper_id = _html.escape(paper_id, quote=True) if paper_id else ""

    # JS template literal context: escape backtick and ${ for safe interpolation
    js_translation = translation.replace("`", "\\`").replace("${", "\\${")

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
            hx-get="/translate-deep/{lemma}?lang={lang}{paper_param}{element_param}{title_param}"
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
    # Note: Use attr_word for context explanation to keep original word as title
    context_btn = ""
    if element_id:
        context_btn = f"""
        <button
            onclick="explainWithContext('{attr_element_id}', '{attr_word}', '{lang}', '{attr_paper_id}')"
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
    <button onclick="saveWordToNote('{attr_word}', `{js_translation}`)" title="Save to Note"
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
        <button onclick="jumpToElement('{attr_element_id}')" title="Jump to word"
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


class ExplainRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=2000)
    lang: str = Field(default="ja")
    paper_id: str | None = None
    paper_title: str | None = None
    session_id: str | None = None
    element_id: str | None = None
    conf: str | None = None
    context: str | None = Field(default=None, max_length=5000)

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        """サポートされている言語コードのみ許可する。"""
        if v not in SUPPORTED_LANGUAGES:
            return "ja"
        return v


@router.post("/translate")
async def explain_post(
    payload: ExplainRequest,
    req: Request,
    storage: ORMStorageAdapter = Depends(get_orm_storage),
):
    """POST版の解説・翻訳エンドポイント (URI長制限への対応)"""
    return await explain(
        req=req,
        word=payload.word,
        lang=payload.lang,
        paper_id=payload.paper_id,
        paper_title=payload.paper_title,
        session_id=payload.session_id,
        element_id=payload.element_id,
        conf=payload.conf,
        context=payload.context,
        storage=storage,
    )


@router.get("/translate/{word}")
async def explain(
    req: Request,
    word: str,
    lang: str = "ja",
    paper_id: str | None = None,
    paper_title: str | None = None,
    session_id: str | None = None,
    element_id: str | None = None,
    conf: str | None = None,
    context: str | None = None,
    storage: ORMStorageAdapter = Depends(get_orm_storage),
):
    """単語の解説 (Cache -> Gemini)"""
    start_time = asyncio.get_event_loop().time()
    element_id = element_id or req.headers.get("HX-Trigger")

    log.info(
        "explain", "Word lookup", word=word, element_id=element_id, paper_id=paper_id
    )

    is_htmx = req.headers.get("HX-Request") == "true"

    # 0. Clean input
    original_word = word
    lemma = _clean_word(word)

    current_user_id = _resolve_user_id(req, session_id)

    # Fetch paper title for local LLM optimization (Skip if title is provided by frontend)
    if not paper_title and paper_id:
        paper_obj = storage.get_paper(paper_id)
        if paper_obj:
            paper_title = paper_obj.get("title")

    # 1. Cache Check / Translation Pod
    cached = await service.get_translation(lemma, lang=lang, context=context, paper_title=paper_title)
    if cached:
        source = cached.get("source", "Cache")
        elapsed = asyncio.get_event_loop().time() - start_time
        log.info(
            "explain",
            "Lookup completed (Cache)",
            elapsed=f"{elapsed:.3f}s",
            word=word,
            paper_id=paper_id,
        )
        return _make_response(
            word=original_word,
            lemma=lemma,
            translation=cached["translation"],
            source=source,
            is_htmx=is_htmx,
            element_id=element_id,
            lang=lang,
            paper_id=paper_id,
            paper_title=paper_title,
        )

    # 2. Gemini Translation
    log.info("explain", "Cache miss, translating with Gemini", lemma=lemma)

    try:
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
        trace_id = None

        # PDF コンテキストキャッシュが存在すれば直接 API 呼び出しで論文全文を活用
        pdf_cache_name = _get_pdf_cache_name(paper_id)

        is_long_text = len(original_word) > 20 or " " in original_word.strip()

        if pdf_cache_name:
            tmpl = SENTENCE_TRANSLATE_FROM_PDF_PROMPT if is_long_text else TRANSLATE_FROM_PDF_PROMPT
            translation = await _generate_with_pdf_cache(
                original_word, context, tmpl, lang_name, pdf_cache_name
            )
            log.info("explain", "Translated with PDF context cache", lemma=lemma)
        else:
            # キャッシュなし: abstract + 周辺テキストで DSPy 経由
            paper_context = _build_paper_context(paper_id, context, storage)

            if is_long_text:
                sent_mod = SentenceTranslationModule()
                res, trace_id = await trace_dspy_call(
                    "SentenceTranslationModule",
                    "SentenceTranslation",
                    sent_mod,
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
                translation = res.translation.strip()
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

        elapsed = asyncio.get_event_loop().time() - start_time
        log.info(
            "explain",
            "Lookup completed (Gemini)",
            elapsed=f"{elapsed:.3f}s",
            word=word,
            paper_id=paper_id,
        )
        return _make_response(
            word=original_word,
            lemma=lemma,
            translation=translation,
            source="Gemini",
            html_source="Gemini AI",
            is_htmx=is_htmx,
            element_id=element_id,
            trace_id=trace_id,
            lang=lang,
            paper_id=paper_id,
            paper_title=paper_title,
        )
    except Exception as e:
        log.error(
            "explain", "Gemini fallback translation failed", error=str(e), lemma=lemma
        )
        error_msg = (
            f"Translation failed: {str(e)}" if is_local() else "Translation failed"
        )
        return _make_response(
            word=original_word,
            lemma=lemma,
            translation=error_msg,
            source="Error",
            is_htmx=is_htmx,
            element_id=element_id,
            lang=lang,
            paper_id=paper_id,
            status_code=500,
        )


@router.get("/translate-deep/{word}")
async def explain_deep(
    req: Request,
    word: str,
    lang: str = "ja",
    paper_id: str | None = None,
    session_id: str | None = None,
    element_id: str | None = None,
    context: str | None = None,
    storage: ORMStorageAdapter = Depends(get_orm_storage),
):
    """Geminiによる詳細翻訳（ユーザー押下により発動）"""
    # Robust element_id detection
    element_id = element_id or req.headers.get("HX-Trigger")

    is_htmx = req.headers.get("HX-Request") == "true"
    start_time = asyncio.get_event_loop().time()
    # 0. Clean input
    original_word = word
    lemma = _clean_word(word)

    current_user_id = _resolve_user_id(req, session_id)

    # Stage 3: Gemini translation
    try:
        lang_name = SUPPORTED_LANGUAGES.get(lang, lang)
        trace_id = None

        log.info("explain_deep", "Gemini call", lemma=lemma)

        # PDF コンテキストキャッシュが存在すれば直接 API 呼び出しで論文全文を活用
        pdf_cache_name = _get_pdf_cache_name(paper_id)

        if pdf_cache_name:
            translation = await _generate_with_pdf_cache(
                original_word, context, TRANSLATE_FROM_PDF_PROMPT, lang_name, pdf_cache_name
            )
            log.info("explain_deep", "Translated with PDF context cache", lemma=lemma)
        else:
            # キャッシュなし: abstract + 周辺テキストで DSPy 経由
            paper_context = _build_paper_context(paper_id, context, storage)

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

        elapsed = asyncio.get_event_loop().time() - start_time
        log.info(
            "explain_deep",
            "Deep lookup completed",
            elapsed=f"{elapsed:.3f}s",
            word=word,
            paper_id=paper_id,
        )
        return _make_response(
            word=original_word,
            lemma=lemma,
            translation=translation,
            source="Gemini",
            html_source="Gemini AI",
            is_htmx=is_htmx,
            element_id=element_id,
            trace_id=trace_id,
            lang=lang,
            paper_id=paper_id,
            show_deep_btn=False,
        )
    except Exception as e:
        log.error(
            "explain_deep", "Gemini translation failed", error=str(e), lemma=lemma
        )
        error_msg = str(e) if is_local() else "An error occurred during translation."
        return _make_response(
            word=original_word,
            lemma=lemma,
            translation=error_msg,
            source="Error",
            is_htmx=is_htmx,
            element_id=element_id,
            lang=lang,
            paper_id=paper_id,
            status_code=500,
        )


class ExplainContextRequest(BaseModel):
    word: str = Field(..., min_length=1, max_length=2000)
    context: str = Field(..., min_length=1, max_length=5000)
    session_id: str | None = None
    lang: str = Field(default="ja")

    @field_validator("lang")
    @classmethod
    def validate_lang(cls, v: str) -> str:
        """サポートされている言語コードのみ許可する。"""
        if v not in SUPPORTED_LANGUAGES:
            return "ja"
        return v


@router.post("/explain/context")
async def explain_with_context(
    req: ExplainContextRequest,
    request: Request,
    storage: ORMStorageAdapter = Depends(get_orm_storage),
):
    """Explain word with context using Gemini"""
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

    current_user_id = _resolve_user_id(request, req.session_id)

    try:
        trace_id = None

        # PDF コンテキストキャッシュが存在すれば直接 API 呼び出しで論文全文を活用
        pdf_cache_name = _get_pdf_cache_name(paper_id)

        is_long_text = len(req.word) > 20 or " " in req.word.strip()

        if pdf_cache_name:
            tmpl = SENTENCE_TRANSLATE_FROM_PDF_PROMPT if is_long_text else EXPLAIN_FROM_PDF_PROMPT
            explanation = await _generate_with_pdf_cache(
                req.word, req.context, tmpl, lang_name, pdf_cache_name
            )
            log.info("explain_context", "Explained with PDF context cache", word=req.word)
        else:
            # キャッシュなし: abstract + 周辺テキストで DSPy 経由
            paper_context = (summary_context + "\n" + req.context).strip()
            trace_ctx = TraceContext(
                user_id=current_user_id, session_id=req.session_id, paper_id=paper_id
            )
            if is_long_text:
                sent_mod = SentenceTranslationModule()
                res, trace_id = await trace_dspy_call(
                    "SentenceTranslationModule",
                    "SentenceTranslation",
                    sent_mod,
                    {
                        "paper_context": paper_context,
                        "target_word": req.word,
                        "user_persona": "Professional Academic Translator",
                        "lang_name": lang_name,
                    },
                    context=trace_ctx,
                )
                explanation = res.translation.strip()
            else:
                trans_mod = TranslationModule()
                res, trace_id = await trace_dspy_call(
                    "TranslationModule",
                    "ContextAwareTranslation",
                    trans_mod,
                    {
                        "paper_context": paper_context,
                        "target_word": req.word,
                        "user_persona": "Professional Academic Translator",
                        "lang_name": lang_name,
                    },
                    context=trace_ctx,
                )
                explanation = res.translation_and_explanation.strip()

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
