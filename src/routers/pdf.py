"""
PDF Analysis & OCR Router
Handles PDF upload, OCR processing, and streaming text analysis.
"""

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import HTMLResponse, Response, StreamingResponse

from ..logger import logger
from ..logic import EnglishAnalysisService
from ..providers import RedisService, get_storage_provider
from ..utils import _get_file_hash

router = APIRouter(tags=["PDF Analysis"])

# Services
service = EnglishAnalysisService()
storage = get_storage_provider()
redis_service = RedisService()


@router.post("/analyze_txt")
async def analyze_txt(html_text: str = Form(...)):
    task_id = str(uuid.uuid4())
    redis_service.set(f"task:{task_id}", {"text": html_text, "paper_id": None}, expire=3600)
    return HTMLResponse(
        f'<div id="paper-content" class="fade-in"></div>'
        f'<div id="sse-container-{task_id}" hx-ext="sse" sse-connect="/stream/{task_id}" '
        f'sse-swap="message" hx-swap="beforeend"></div>'
    )


@router.post("/analyze-pdf")
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


@router.get("/stream/{task_id}")
async def stream(task_id: str):
    import time

    stream_start = time.time()
    logger.info(f"[stream] START: task_id={task_id}")

    data = redis_service.get(f"task:{task_id}")

    # タスクが存在しない場合は HTTP 204 No Content を返す
    if not data:
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
                page_image_url,
                layout_data,
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

                # レイアウトデータがある場合は「PDFそのまま表示モード」
                if layout_data and page_image_url:
                    img_w = layout_data["width"]
                    img_h = layout_data["height"]
                    words_html = []

                    for w in layout_data["words"]:
                        bbox = w["bbox"]
                        # パーセント計算
                        left = (bbox[0] / img_w) * 100
                        top = (bbox[1] / img_h) * 100
                        width = ((bbox[2] - bbox[0]) / img_w) * 100
                        height = ((bbox[3] - bbox[1]) / img_h) * 100
                        word_text = w["word"]

                        # 透明なクリック領域を作成
                        words_html.append(
                            f'<a class="absolute cursor-pointer hover:bg-yellow-300/30 transition-colors rounded-sm group"'
                            f' style="left:{left}%; top:{top}%; width:{width}%; height:{height}%;"'
                            f' hx-get="/explain/{word_text}"'
                            f' hx-trigger="click"'
                            f' hx-target="#definition-box"'
                            f' hx-swap="afterbegin">'
                            f"</a>"
                        )

                    full_words_html = "".join(words_html)

                    # コンテナ出力
                    yield f'event: message\ndata: <div id="{page_container_id}" hx-swap-oob="beforeend:#paper-content" class="mb-10 bg-white shadow-sm rounded-2xl animate-fade-in overflow-hidden max-w-4xl mx-auto"><div class="flex justify-between items-center px-6 py-4 border-b border-slate-100 bg-slate-50/50"><span class="text-xs text-slate-400 font-bold uppercase tracking-wide">Page {page_num}/{total_pages}</span><span class="text-[10px] text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded-full font-medium">Interactive PDF</span></div><div class="relative w-full"><img src="{page_image_url}" alt="Page {page_num}" class="w-full h-auto block select-none" loading="lazy"><div class="absolute inset-0 w-full h-full">{full_words_html}</div></div></div>\n\n'

                # レイアウトデータがない場合（OCRフォールバック）は既存の表示モード
                else:
                    # ページの枠を #paper-content に追記（2カラムレイアウト：画像 + テキスト）
                    if page_image_url:
                        # 画像がある場合（URLパス）：2カラムレイアウト
                        yield f'event: message\ndata: <div id="{page_container_id}" hx-swap-oob="beforeend:#paper-content" class="mb-10 bg-white shadow-sm rounded-2xl animate-fade-in overflow-hidden"><div class="flex justify-between items-center px-6 py-4 border-b border-slate-100 bg-slate-50/50"><span class="text-xs text-slate-400 font-bold uppercase tracking-wide">Page {page_num}/{total_pages}</span><span class="text-[10px] text-green-500 bg-green-50 px-2 py-0.5 rounded-full font-medium">Ready</span></div><div class="grid grid-cols-1 lg:grid-cols-2 gap-0"><div class="p-4 bg-slate-50 border-r border-slate-100 flex items-start justify-center"><img src="{page_image_url}" alt="Page {page_num}" class="max-w-full h-auto rounded-lg shadow-sm border border-slate-200" loading="lazy"></div><div id="{content_id}" class="p-6 overflow-y-auto max-h-[800px]"></div></div></div>\n\n'
                    else:
                        # 画像がない場合（キャッシュ）：テキストのみ
                        yield f'event: message\ndata: <div id="{page_container_id}" hx-swap-oob="beforeend:#paper-content" class="mb-10 p-6 md:p-8 bg-white shadow-sm rounded-2xl animate-fade-in"><div class="flex justify-between items-center mb-6 border-b border-slate-100 pb-3"><span class="text-xs text-slate-300 font-bold uppercase tracking-wide">Page {page_num}/{total_pages}</span><span class="text-[10px] text-green-500 bg-green-50 px-2 py-0.5 rounded-full font-medium">Cached</span></div><div id="{content_id}" class="max-w-prose"></div></div>\n\n'

                    # ページ内のテキストを即座にトークン化してクリック可能なHTMLをストリーム表示
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
                logger.info(f"Paper saved completed: {paper_id}")
            except Exception as e:
                logger.error(f"Failed to save paper: {e}")

            # セッションコンテキスト保存
            if session_id:
                redis_service.set(f"session:{session_id}", full_text, expire=86400)

            # 完了処理
            redis_service.delete(f"task:{task_id}")
            # フロントエンドにpaper_idを通知
            yield f'event: message\ndata: <input type="hidden" id="current-paper-id" value="{paper_id}" hx-swap-oob="true" />\n\n'
            # data-paper-id 更新が画面消失のトリガーになっている可能性があるため削除
            yield f'event: message\ndata: <div id="sse-container-{task_id}" hx-swap-oob="outerHTML" style="display:none"></div>\n\n'
            yield "event: close\ndata: done\n\n"

        return StreamingResponse(ocr_generate(), media_type="text/event-stream")

    # キャッシュされたHTMLがある場合の処理
    if text.startswith("CACHED_HTML:"):
        html_content = text[12:]
        logger.info(f"[stream] Serving cached HTML for paper_id={paper_id}")

        async def cached_generate():
            # キャッシュされたHTMLを表示（paper-contentの中身を置換）
            yield f'event: message\ndata: <div id="paper-content" hx-swap-oob="innerHTML">{html_content}</div>\n\n'

            # HTMXを再処理させるためのスクリプト
            yield 'event: message\ndata: <script hx-swap-oob="beforeend:body">htmx.process(document.getElementById("paper-content"));</script>\n\n'

            # 辞書準備完了表示
            yield 'event: message\ndata: <div id="definition-box" hx-swap-oob="innerHTML"><div id="dict-empty-state" class="min-h-[200px] flex flex-col items-center justify-center text-center p-6 border-2 border-dashed border-slate-100 rounded-2xl"><div class="bg-slate-50 p-3 rounded-xl mb-3"><svg class="w-6 h-6 text-slate-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"></path></svg></div><p class="text-[10px] font-bold text-slate-400 leading-relaxed">Dictionary Ready!<br>Click any word for definition.</p></div></div>\n\n'

            # 完了ステータス
            yield 'event: message\ndata: <div id="tokenize-status" hx-swap-oob="true" class="fixed bottom-4 right-4 bg-green-500 text-white px-4 py-2 rounded-lg shadow-lg">✅ 読込完了（キャッシュ）</div>\n\n'
            # フロントエンドにpaper_idを通知
            yield f'event: message\ndata: <input type="hidden" id="current-paper-id" value="{paper_id}" hx-swap-oob="true" />\n\n'

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
        # フロントエンドにpaper_idを通知
        yield f'event: message\ndata: <input type="hidden" id="current-paper-id" value="{paper_id}" hx-swap-oob="true" />\n\n'

        # ストリーム終了時に、SSEコンテナ自体を通常のdivに置換して接続を物理的に切断する
        yield f'event: message\ndata: <div id="sse-container-{task_id}" hx-swap-oob="outerHTML" data-paper-id="finished" style="display:none"></div>\n\n'

        # 念のためcloseイベントも送る
        yield "event: close\ndata: done\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
