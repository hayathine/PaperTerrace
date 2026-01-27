import asyncio
import os
import uuid
from typing import Optional

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, File, Form, Request, UploadFile
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
from .providers import RedisService, get_storage_provider
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
redis_service = RedisService()

# In-memory storage replaced by Redis
# text_storage and session_contexts are now managed via redis_service


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
    redis_service.set(f"task:{task_id}", {"text": html_text, "paper_id": None}, expire=3600)
    return HTMLResponse(
        f'<div id="paper-content" class="fade-in"></div>'
        f'<div id="sse-container-{task_id}" hx-ext="sse" sse-connect="/stream/{task_id}" '
        f'sse-swap="message" hx-swap="beforeend"></div>'
    )


@app.post("/analyze-pdf")
async def analyze_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
):
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

    import time

    start_time = time.time()
    logger.info(f"[analyze-pdf] START: {file.filename} ({file.size} bytes)")

    content = await file.read()
    file_hash = _get_file_hash(content)
    logger.info(f"[analyze-pdf] File hash computed: {file_hash[:16]}...")

    # Check for cached paper
    cached_paper = storage.get_paper_by_hash(file_hash)
    if cached_paper:
        paper_id = cached_paper["paper_id"]
        logger.info(f"[analyze-pdf] Cache HIT: paper_id={paper_id}")
        # HTMLコンテンツがあればそれを使用
        if cached_paper.get("html_content"):
            raw_text = "CACHED_HTML:" + cached_paper["html_content"]
            logger.info(f"[analyze-pdf] Using cached HTML for paper: {paper_id}")
        else:
            raw_text = cached_paper["ocr_text"]
            logger.info(f"[analyze-pdf] Using cached OCR text for paper: {paper_id}")

        # Store context for session
        if session_id:
            context_text = raw_text[12:] if raw_text.startswith("CACHED_HTML:") else raw_text
            redis_service.set(f"session:{session_id}", context_text, expire=86400)
    else:
        # OCR未処理：PDFデータをRedisに保存し、streamで処理
        logger.info(f"[analyze-pdf] Cache MISS: Deferring OCR to stream for {file.filename}")
        import base64

        pdf_b64 = base64.b64encode(content).decode("utf-8")
        raw_text = None  # ストリームでOCR処理する
        paper_id = "pending"  # ストリーム内で設定される

    # 正常な場合はIDを発行してストリームへ
    task_id = str(uuid.uuid4())

    if raw_text is None:
        # OCR未処理：PDFデータを保存
        redis_service.set(
            f"task:{task_id}",
            {
                "pending_ocr": True,
                "pdf_b64": pdf_b64,
                "file_hash": file_hash,
                "filename": file.filename,
                "session_id": session_id,
            },
            expire=3600,
        )
    else:
        # キャッシュヒット：テキストを保存
        redis_service.set(f"task:{task_id}", {"text": raw_text, "paper_id": paper_id}, expire=3600)

    total_elapsed = time.time() - start_time
    logger.info(
        f"[analyze-pdf] Task created: {task_id}, paper_id={paper_id}, total time: {total_elapsed:.2f}s"
    )
    logger.info(
        f"[analyze-pdf] END: Returning SSE container, stream will start at /stream/{task_id}"
    )

    # コンテナにIDを付与して、後で置換できるようにする
    return HTMLResponse(
        f'<div id="paper-content" class="fade-in"></div>'
        f'<div id="sse-container-{task_id}" hx-ext="sse" sse-connect="/stream/{task_id}" '
        f'sse-swap="message" hx-swap="beforeend" data-paper-id="{paper_id}"></div>'
    )


@app.get("/stream/{task_id}")
async def stream(task_id: str):
    import time

    stream_start = time.time()
    logger.info(f"[stream] START: task_id={task_id}")

    data = redis_service.get(f"task:{task_id}")

    # タスクが存在しない場合は HTTP 204 No Content を返す
    if not data:
        from fastapi import Response

        logger.warning(f"[stream] Task not found: {task_id}")
        return Response(status_code=204)

    # Redisから取得したデータは辞書型になっているはず
    text = data.get("text", "")
    paper_id = data.get("paper_id")
    logger.info(f"[stream] Task data retrieved: paper_id={paper_id}, text_length={len(text)}")

    # OCR未実行の場合：ストリーム内でOCR処理を行う
    if data.get("pending_ocr"):
        import base64

        pdf_b64 = data.get("pdf_b64", "")
        file_hash = data.get("file_hash", "")
        filename = data.get("filename", "unknown.pdf")
        session_id = data.get("session_id")
        pdf_content = base64.b64decode(pdf_b64)

        async def ocr_generate():
            import uuid6

            # OCR処理中の表示
            yield 'event: message\ndata: <div id="paper-content" hx-swap-oob="innerHTML"><div class="flex flex-col items-center justify-center min-h-[400px] text-center"><div class="animate-spin rounded-full h-12 w-12 border-4 border-indigo-200 border-t-indigo-600 mb-4"></div><p class="text-slate-500 font-medium">📄 PDFを解析中...</p><p class="text-xs text-slate-400 mt-2">AI OCRで文字認識を実行しています<br>ページごとに順次表示されます</p></div></div>\n\n'

            full_text_fragments = []

            # ページ単位OCRストリーム
            async for (
                page_num,
                total_pages,
                page_text,
                is_last,
                f_hash,
            ) in service.ocr_service.extract_text_streaming(pdf_content, filename):
                # APIエラーチェック
                if page_text.startswith("ERROR_API_FAILED:"):
                    error_detail = page_text.replace("ERROR_API_FAILED: ", "")
                    yield (
                        f"event: message\ndata: <div id='paper-content' hx-swap-oob='innerHTML'>"
                        f"<div class='p-6 bg-red-50 border-2 border-red-200 rounded-2xl text-red-700'>"
                        f"<h3 class='font-bold mb-2'>⚠️ AI解析エラー</h3>"
                        f"<p class='text-xs opacity-80 mb-4'>APIの呼び出しに失敗しました。</p>"
                        f"<div class='bg-white/50 p-3 rounded-lg font-mono text-[10px] break-all'>{error_detail}</div>"
                        f"</div></div>\n\n"
                    )
                    yield f'event: message\ndata: <div id="sse-container-{task_id}" hx-swap-oob="outerHTML" style="display:none"></div>\n\n'
                    yield "event: close\ndata: done\n\n"
                    redis_service.delete(f"task:{task_id}")
                    return

                full_text_fragments.append(page_text)

                # 初回（1ページ目）はローディング表示をクリア
                if page_num == 1:
                    yield 'event: message\ndata: <div id="paper-content" hx-swap-oob="innerHTML"></div>\n\n'

                # ページコンテナ作成
                page_container_id = f"page-{page_num}"
                content_id = f"content-{page_container_id}"

                # ページの枠を追加
                yield f'event: message\ndata: <div id="paper-content" hx-swap="beforeend"><div id="{page_container_id}" class="mb-8 p-4 bg-white shadow-sm rounded-xl min-h-[500px] animate-fade-in"><div class="flex justify-between items-center mb-4 border-b border-slate-100 pb-2"><span class="text-xs text-slate-300 font-bold uppercase">Page {page_num}/{total_pages}</span><span class="text-[10px] text-green-500 bg-green-50 px-2 py-0.5 rounded-full">Ready</span></div><div id="{content_id}"></div></div></div>\n\n'

                # ページ内のテキストをトークン化してストリーム表示
                page_prefix = f"p-pg{page_num}"

                async for chunk in service.tokenize_stream(
                    page_text,
                    paper_id=None,
                    target_id=content_id,
                    id_prefix=page_prefix,
                    save_to_db=False,
                ):
                    yield chunk
                    await asyncio.sleep(0.005)

            # 全ページ完了後、DB保存
            full_text = "\n\n---\n\n".join(full_text_fragments)
            paper_id = str(uuid6.uuid7())

            try:
                storage.save_paper(
                    paper_id=paper_id,
                    file_hash=file_hash,
                    filename=filename,
                    ocr_text=full_text,
                    html_content="",
                    target_language="ja",
                )
                logger.info(f"Paper saved during stream: {paper_id}")
            except Exception as e:
                logger.error(f"Failed to save paper: {e}")

            # セッションコンテキスト保存
            if session_id:
                redis_service.set(f"session:{session_id}", full_text, expire=86400)

            # 完了処理
            redis_service.delete(f"task:{task_id}")
            yield f'event: message\ndata: <div id="sse-container-{task_id}" hx-swap-oob="outerHTML" data-paper-id="{paper_id}" style="display:none"></div>\n\n'
            yield "event: close\ndata: done\n\n"

        return StreamingResponse(ocr_generate(), media_type="text/event-stream")

    # キャッシュされたHTMLがある場合の処理
    if text.startswith("CACHED_HTML:"):
        html_content = text[12:]
        logger.info(f"[stream] Serving cached HTML for paper_id={paper_id}")

        async def cached_generate():
            # キャッシュされたHTMLを表示（paper-contentの中身を置換）
            yield f'event: message\ndata: <div id="paper-content" hx-swap-oob="innerHTML">{html_content}</div>\n\n'

            # 完了ステータス
            yield 'event: message\ndata: <div id="tokenize-status" hx-swap-oob="true" class="fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg">✅ 読込完了（キャッシュ）</div>\n\n'

            # SSEコンテナを削除して接続終了
            yield f'event: message\ndata: <div id="sse-container-{task_id}" hx-swap-oob="outerHTML" data-paper-id="finished" style="display:none"></div>\n\n'
            yield "event: close\ndata: done\n\n"
            logger.info(
                f"[stream] END (cached): task_id={task_id}, elapsed={time.time() - stream_start:.2f}s"
            )

        redis_service.delete(f"task:{task_id}")
        return StreamingResponse(cached_generate(), media_type="text/event-stream")

    logger.info(f"[stream] Starting tokenization for paper_id={paper_id}")

    async def generate():
        async for chunk in service.tokenize_stream(text, paper_id):
            yield chunk
            await asyncio.sleep(0.01)

        redis_service.delete(f"task:{task_id}")
        logger.info(
            f"[stream] END: task_id={task_id}, paper_id={paper_id}, elapsed={time.time() - stream_start:.2f}s"
        )

        # ストリーム終了時に、SSEコンテナ自体を通常のdivに置換して接続を物理的に切断する
        yield f'event: message\ndata: <div id="sse-container-{task_id}" hx-swap-oob="outerHTML" data-paper-id="finished" style="display:none"></div>\n\n'

        # 念のためcloseイベントも送る
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
        f'<div class="p-4 rounded-lg {bg_class} border animate-fade-in">'
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
            f'<div class="p-4 rounded-lg {bg} border animate-fade-in"><b>{cached["word"]}</b>'
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
            f'<div class="p-4 rounded-lg bg-blue-50 border animate-fade-in"><b>{lemma}</b>'
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
    context = redis_service.get(f"session:{request.session_id}") or ""

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
    context = redis_service.get(f"session:{session_id}") or ""
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
    context = redis_service.get(f"session:{session_id}") or ""
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    papers = await research_radar_service.find_related_papers(context[:3000])
    queries = await research_radar_service.generate_search_queries(context[:3000])
    return JSONResponse({"related_papers": papers, "search_queries": queries})


@app.post("/analyze-citations")
async def analyze_citations(session_id: str = Form(...)):
    context = redis_service.get(f"session:{session_id}") or ""
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    citations = await research_radar_service.analyze_citations(context)
    return JSONResponse({"citations": citations})


# ============================================================================
# Paragraph Explanation
# ============================================================================


@app.post("/explain-paragraph")
async def explain_paragraph(paragraph: str = Form(...), session_id: str = Form(...)):
    context = redis_service.get(f"session:{session_id}") or ""
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
    context = redis_service.get(f"session:{session_id}") or ""
    analysis = await figure_insight_service.analyze_table_text(table_text, context)
    return JSONResponse({"analysis": analysis})


# ============================================================================
# Adversarial Review
# ============================================================================


@app.post("/critique")
async def critique(session_id: str = Form(...)):
    context = redis_service.get(f"session:{session_id}") or ""
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    critique = await adversarial_service.critique(context)
    return JSONResponse(critique)


@app.post("/identify-limitations")
async def identify_limitations(session_id: str = Form(...)):
    context = redis_service.get(f"session:{session_id}") or ""
    if not context:
        return JSONResponse({"error": "論文が読み込まれていません"}, status_code=400)

    limitations = await adversarial_service.identify_limitations(context)
    return JSONResponse({"limitations": limitations})


@app.post("/counterarguments")
async def counterarguments(claim: str = Form(...), session_id: str = Form("")):
    context = redis_service.get(f"session:{session_id}") or ""
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
