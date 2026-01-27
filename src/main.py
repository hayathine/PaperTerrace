import asyncio
import os
import uuid
from typing import Optional

import uuid6
from dotenv import load_dotenv
from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .feature import (
    AdversarialReviewService,
    ChatService,
    FigureInsightService,
    ParagraphExplainService,
    ResearchRadarService,
    SidebarMemoService,
    SummaryService,
    TranslationService,
)
from .logger import logger
from .logic import EnglishAnalysisService
from .providers import get_storage_provider
from .routers import auth_router, explore_router, users_router
from .utils import _get_file_hash

app = FastAPI(
    title="PaperTerrace",
    description="AI-powered paper reading assistant",
    version="1.0.0",
)


# Load environment variables
load_dotenv()

# Firebase Config for Frontend
FIREBASE_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
}

# Templates and static files
templates = Jinja2Templates(directory="src/templates")
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# Include routers
app.include_router(auth_router)
app.include_router(users_router)
app.include_router(explore_router)

# Services
service = EnglishAnalysisService()
translation_service = TranslationService()
chat_service = ChatService()
summary_service = SummaryService()
research_radar_service = ResearchRadarService()
paragraph_explain_service = ParagraphExplainService()
figure_insight_service = FigureInsightService()
adversarial_service = AdversarialReviewService()
sidebar_memo_service = SidebarMemoService()
storage = get_storage_provider()

# In-memory storage for SSE and sessions
text_storage: dict[str, str] = {}
session_contexts: dict[str, str] = {}  # session_id -> paper_text


# ============================================================================
# Request/Response Models
# ============================================================================


class ChatRequest(BaseModel):
    message: str
    session_id: str
    author_mode: bool = False


class MemoRequest(BaseModel):
    session_id: str
    term: str
    note: str


class LanguageSettingRequest(BaseModel):
    session_id: str
    language: str


# ============================================================================
# Main Pages
# ============================================================================


@app.get("/", response_class=HTMLResponse)
async def read_item(request: Request):
    return templates.TemplateResponse(
        "index.html", {"request": request, "firebase_config": FIREBASE_CONFIG}
    )


# ============================================================================
# PDF Analysis & OCR
# ============================================================================


@app.post("/analyze_txt")
async def analyze_txt(html_text: str = Form(...)):
    task_id = str(uuid.uuid4())
    text_storage[task_id] = html_text
    return HTMLResponse(
        f'<div hx-ext="sse" sse-connect="/stream/{task_id}" sse-swap="message"'
        ' hx-swap="beforeend"></div>'
    )


@app.post("/analyze-pdf")
async def analyze_pdf(file: UploadFile = File(...), session_id: Optional[str] = Form(None)):
    # ファイル名がない、またはサイズが0の場合はエラーを返す
    if not file.filename or file.size == 0:

        async def error_stream():
            yield (
                "data: <div class='p-6 bg-amber-50 border-2 border-amber-200 "
                "rounded-2xl text-amber-700 animate-fade-in'>"
                "<h3 class='font-bold mb-2'>⚠️ ファイルが未選択です</h3>"
                "<p class='text-xs opacity-80'>解析するPDFファイルをアップロードしてください。</p>"
                "</div>\n\n"
            )

        return StreamingResponse(error_stream(), media_type="text/event-stream")

    content = await file.read()
    file_hash = _get_file_hash(content)

    # Check for cached paper
    cached_paper = storage.get_paper_by_hash(file_hash)
    if cached_paper:
        raw_text = cached_paper["ocr_text"]
        paper_id = cached_paper["paper_id"]
    else:
        # AI OCR を実行
        raw_text = await service.ocr_service.extract_text_with_ai(content, file.filename)

        # APIエラーが返ってきた場合の処理
        if raw_text.startswith("ERROR_API_FAILED:"):
            error_detail = raw_text.replace("ERROR_API_FAILED: ", "")

            async def error_stream():
                yield (
                    f"data: <div class='p-6 bg-red-50 border-2 border-red-200 "
                    f"rounded-2xl text-red-700 animate-fade-in'>"
                    f"<h3 class='font-bold mb-2'>⚠️ AI解析エラー</h3>"
                    f"<p class='text-xs opacity-80 mb-4'>APIの呼び出しに失敗しました。</p>"
                    f"<div class='bg-white/50 p-3 rounded-lg font-mono text-[10px] "
                    f"break-all'>{error_detail}</div></div>\n\n"
                )

            return StreamingResponse(error_stream(), media_type="text/event-stream")

        # Save paper to database
        paper_id = str(uuid6.uuid7())
        storage.save_paper(
            paper_id=paper_id,
            file_hash=file_hash,
            filename=file.filename,
            ocr_text=raw_text,
            html_content="",  # Will be generated during stream
            target_language="ja",
        )

    # Store context for session
    if session_id:
        session_contexts[session_id] = raw_text

    # 正常な場合はIDを発行してストリームへ
    task_id = str(uuid.uuid4())
    text_storage[task_id] = raw_text
    return HTMLResponse(
        f'<div hx-ext="sse" sse-connect="/stream/{task_id}" sse-swap="message" '
        f'sse-close="close" hx-swap="beforeend" data-paper-id="{paper_id}"></div>'
    )


@app.get("/stream/{task_id}")
async def stream(task_id: str):
    text = text_storage.get(task_id, "")

    # タスクが存在しない場合は即座に終了イベントを送信
    if not text:

        async def empty_stream():
            # SSEの終了を通知して再接続を防ぐ
            yield "event: close\ndata: done\n\n"

        return StreamingResponse(empty_stream(), media_type="text/event-stream")

    async def generate():
        async for chunk in service.tokenize_stream(text):
            yield chunk
            await asyncio.sleep(0.01)
        if task_id in text_storage:
            del text_storage[task_id]
        # ストリーム終了を明示的に通知
        yield "event: close\ndata: done\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ============================================================================
# Translation
# ============================================================================


@app.get("/translate/{word}")
async def translate_word(word: str, lang: str = "ja"):
    result = await translation_service.translate_word(word, lang)
    bg_class = "bg-blue-50" if result["source"] == "cache" else "bg-purple-50"
    return HTMLResponse(
        f'<div class="p-4 rounded-lg {bg_class} border animate-in">'
        f"<b>{result['word']}</b>"
        f"<p>{result['translation']}</p>"
        f"<small class='text-slate-400'>{result['target_lang']}</small>"
        f"</div>"
    )


@app.get("/explain/{lemma}")
async def explain(lemma: str):
    """単語の説明を取得（キャッシュ → Jamdict → Gemini の順で検索）"""
    # まずキャッシュから翻訳を取得
    cached = service.get_translation(lemma)
    if cached:
        bg = "bg-purple-50"
        return HTMLResponse(
            f'<div class="p-4 rounded-lg {bg} border animate-in"><b>{cached["word"]}</b>'
            f"<p>{cached['translation']}</p>"
            f'<small class="text-slate-400">{cached["source"]}</small></div>'
        )

    # キャッシュにない場合は Jamdict を検索
    from concurrent.futures import ThreadPoolExecutor

    from .logic import _lookup_word_full

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
            f'<div class="p-4 rounded-lg bg-blue-50 border animate-in"><b>{lemma}</b>'
            f"<p>{translation}</p>"
            f'<small class="text-slate-400">Jamdict</small></div>'
        )

    # Jamdict にもない場合は Gemini で個別翻訳
    try:
        import os

        import google.genai as genai

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
        model = os.getenv("OCR_MODEL") or "gemini-1.5-flash"
        prompt = f"英単語「{lemma}」の日本語訳を1〜3語で簡潔に。訳のみ出力。"

        res = client.models.generate_content(model=model, contents=prompt)
        translation = res.text.strip() if res.text else "翻訳できませんでした"

        # キャッシュに保存（次回以降は高速に）
        service.translation_cache[lemma] = translation
        service.word_cache[lemma] = False  # Jamdictにはない

        return HTMLResponse(
            f'<div class="p-4 rounded-lg bg-amber-50 border animate-in"><b>{lemma}</b>'
            f"<p>{translation}</p>"
            f'<small class="text-slate-400">Gemini</small></div>'
        )
    except Exception as e:
        logger.error(f"Gemini translation failed for '{lemma}': {e}")
        return HTMLResponse(
            f'<div class="p-4 rounded-lg bg-gray-50 border animate-in"><b>{lemma}</b>'
            f"<p>翻訳に失敗しました</p>"
            f'<small class="text-slate-400">Error</small></div>'
        )


@app.get("/languages")
async def get_languages():
    return JSONResponse(translation_service.get_supported_languages())


@app.post("/settings/language")
async def set_language(request: LanguageSettingRequest):
    # Store language preference (could be in session or database)
    return JSONResponse({"status": "ok", "language": request.language})


# ============================================================================
# Chat
# ============================================================================


@app.post("/chat")
async def chat(request: ChatRequest):
    context = session_contexts.get(request.session_id, "")

    if request.author_mode:
        response = await chat_service.author_agent_response(request.message, context)
    else:
        response = await chat_service.chat(request.message, context)

    return JSONResponse({"response": response})


@app.post("/chat/clear")
async def clear_chat(session_id: str = Form(...)):
    chat_service.clear_history()
    return JSONResponse({"status": "ok"})


# ============================================================================
# Summary
# ============================================================================


@app.post("/summarize")
async def summarize(session_id: str = Form(...), mode: str = Form("full")):
    context = session_contexts.get(session_id, "")
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    if mode == "sections":
        sections = await summary_service.summarize_sections(context)
        return JSONResponse({"sections": sections})
    elif mode == "abstract":
        abstract = await summary_service.summarize_abstract(context)
        return JSONResponse({"abstract": abstract})
    else:
        summary = await summary_service.summarize_full(context)
        return JSONResponse({"summary": summary})


# ============================================================================
# Research Radar
# ============================================================================


@app.post("/research-radar")
async def research_radar(session_id: str = Form(...)):
    context = session_contexts.get(session_id, "")
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    papers = await research_radar_service.find_related_papers(context[:3000])
    queries = await research_radar_service.generate_search_queries(context[:3000])
    return JSONResponse({"related_papers": papers, "search_queries": queries})


@app.post("/analyze-citations")
async def analyze_citations(session_id: str = Form(...)):
    context = session_contexts.get(session_id, "")
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    citations = await research_radar_service.analyze_citations(context)
    return JSONResponse({"citations": citations})


# ============================================================================
# Paragraph Explanation
# ============================================================================


@app.post("/explain-paragraph")
async def explain_paragraph(paragraph: str = Form(...), session_id: str = Form(...)):
    context = session_contexts.get(session_id, "")
    explanation = await paragraph_explain_service.explain(paragraph, context)
    return JSONResponse({"explanation": explanation})


@app.post("/explain-terms")
async def explain_terms(paragraph: str = Form(...)):
    terms = await paragraph_explain_service.explain_terminology(paragraph)
    return JSONResponse({"terms": terms})


# ============================================================================
# Figure Insight
# ============================================================================


@app.post("/analyze-figure")
async def analyze_figure(file: UploadFile = File(...), caption: str = Form("")):
    content = await file.read()
    mime_type = file.content_type or "image/png"
    analysis = await figure_insight_service.analyze_figure(content, caption, mime_type)
    return JSONResponse({"analysis": analysis})


@app.post("/analyze-table")
async def analyze_table(table_text: str = Form(...), session_id: str = Form("")):
    context = session_contexts.get(session_id, "")
    analysis = await figure_insight_service.analyze_table_text(table_text, context)
    return JSONResponse({"analysis": analysis})


# ============================================================================
# Adversarial Review
# ============================================================================


@app.post("/critique")
async def critique(session_id: str = Form(...)):
    context = session_contexts.get(session_id, "")
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    critique = await adversarial_service.critique(context)
    return JSONResponse(critique)


@app.post("/identify-limitations")
async def identify_limitations(session_id: str = Form(...)):
    context = session_contexts.get(session_id, "")
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    limitations = await adversarial_service.identify_limitations(context)
    return JSONResponse({"limitations": limitations})


@app.post("/counterarguments")
async def counterarguments(claim: str = Form(...), session_id: str = Form("")):
    context = session_contexts.get(session_id, "")
    args = await adversarial_service.suggest_counterarguments(claim, context)
    return JSONResponse({"counterarguments": args})


# ============================================================================
# Sidebar Memos
# ============================================================================


@app.get("/memo/{session_id}")
async def get_memos(session_id: str):
    memos = sidebar_memo_service.get_memos(session_id)
    return JSONResponse({"memos": memos})


@app.post("/memo")
async def add_memo(request: MemoRequest):
    memo = sidebar_memo_service.add_memo(request.session_id, request.term, request.note)
    return JSONResponse(memo)


@app.delete("/memo/{memo_id}")
async def delete_memo(memo_id: str):
    deleted = sidebar_memo_service.delete_memo(memo_id)
    return JSONResponse({"deleted": deleted})


@app.post("/memo/export")
async def export_memos(session_id: str = Form(...)):
    export_text = sidebar_memo_service.export_memos(session_id)
    return JSONResponse({"export": export_text})


# ============================================================================
# Paper Management
# ============================================================================


@app.get("/papers")
async def list_papers(limit: int = 50):
    papers = storage.list_papers(limit)
    return JSONResponse({"papers": papers})


@app.get("/papers/{paper_id}")
async def get_paper(paper_id: str):
    paper = storage.get_paper(paper_id)
    if not paper:
        return JSONResponse({"error": "Paper not found"}, status_code=404)
    return JSONResponse(paper)


@app.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str):
    deleted = storage.delete_paper(paper_id)
    return JSONResponse({"deleted": deleted})
