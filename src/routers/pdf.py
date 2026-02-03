"""
PDF Analysis & OCR Router
Handles PDF upload, OCR processing, and streaming text analysis.
"""

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from src.auth import OptionalUser
from src.domain.features import SummaryService
from src.domain.services.analysis_service import EnglishAnalysisService
from src.domain.services.cloud_tasks_service import get_cloud_tasks_service
from src.logger import get_service_logger, logger
from src.providers import RedisService, get_storage_provider
from src.utils import _get_file_hash

log = get_service_logger("PDF")

router = APIRouter(tags=["PDF Analysis"])

# Services


# Services
service = EnglishAnalysisService()
summary_service = SummaryService()
storage = get_storage_provider()
redis_service = RedisService()
cloud_tasks_service = get_cloud_tasks_service()


@router.post("/analyze-pdf")
async def analyze_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    lang: str = Form("ja"),
    user: OptionalUser = None,
):
    """
    Standard HTML version of analyze-pdf for HTMX.
    Returns HTML with SSE connection.
    """
    # Reuse JSON logic but return HTML
    # We can call analyze_pdf_json but we need to unpack the response or refactor
    # To save space, let's just copy the logic and adapt default format.

    if not file.filename or file.size == 0:
        return Response("Error: No file", status_code=400)

    user_id = user.uid if user else None

    content = await file.read()
    file_hash = _get_file_hash(content)

    # Language detection
    detected_lang = await service.ocr_service.detect_language_from_pdf(content)
    if detected_lang and detected_lang != "en":
        logger.warning(f"Unsupported language detected: {detected_lang}")
        return Response(
            "Error: Currently, only English papers are supported. / 現在、英語の論文のみサポートしています。",
            status_code=400,
        )
    if detected_lang:
        lang = detected_lang

    # Cache check
    cached_paper = storage.get_paper_by_hash(file_hash)
    raw_text = None
    paper_id = "pending"
    import base64

    pdf_b64 = None

    if cached_paper:
        paper_id = cached_paper["paper_id"]
        if cached_paper.get("ocr_text"):
            raw_text = cached_paper["ocr_text"]
    else:
        pdf_b64 = base64.b64encode(content).decode("utf-8")

    task_id = str(uuid.uuid4())

    task_data = {
        "format": "html",  # Default for HTMX
        "lang": lang,
        "session_id": session_id,
        "filename": file.filename,
        "file_hash": file_hash,
        "user_id": user_id,
    }

    if raw_text is None:
        task_data.update({"pending_ocr": True, "pdf_b64": pdf_b64})
    else:
        task_data.update({"text": raw_text, "paper_id": paper_id})

    redis_service.set(f"task:{task_id}", task_data, expire=3600)

    return HTMLResponse(f"""
    <div hx-ext="sse" sse-connect="/stream/{task_id}" sse-swap="message">
        <div id="paper-content">
             <div class="flex flex-col items-center justify-center min-h-[400px] text-center">
               <div class="animate-spin rounded-full h-12 w-12 border-4 border-indigo-200 border-t-indigo-600 mb-4"></div>
               <p class="text-slate-500 font-medium">Starting analysis...</p>
           </div>
        </div>
    </div>
    """)


@router.post("/analyze-pdf-json")
async def analyze_pdf_json(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(None),
    lang: str = Form("ja"),
    user: OptionalUser = None,
):
    """
    JSON version of analyze-pdf for React frontend.
    Returns { "task_id": "...", "stream_url": "/stream/..." }
    """
    if not file.filename or file.size == 0:
        return JSONResponse({"error": "No file provided"}, status_code=400)

    import time

    start_time = time.time()
    logger.info(f"[analyze-pdf-json] START: {file.filename} ({file.size} bytes)")

    # Capture user_id
    user_id = user.uid if user else None
    if user_id:
        logger.info(f"[analyze-pdf-json] Authenticated user: {user_id}")

    content = await file.read()
    file_hash = _get_file_hash(content)
    logger.info(f"[analyze-pdf-json] session_id={session_id}, file_hash={file_hash}")

    # Detect PDF language
    detected_lang = await service.ocr_service.detect_language_from_pdf(content)
    if detected_lang and detected_lang != "en":
        logger.warning(f"Unsupported language detected: {detected_lang}")
        return JSONResponse(
            {
                "error": "Currently, only English papers are supported. / 現在、英語の論文のみサポートしています。"
            },
            status_code=400,
        )
    if detected_lang:
        lang = detected_lang

    # Check for cached paper
    cached_paper = storage.get_paper_by_hash(file_hash)
    raw_text = None
    paper_id = "pending"
    import base64

    pdf_b64 = None

    if cached_paper:
        from ..providers.image_storage import get_page_images

        # If cached, we might want to update owner if it was anonymous before?
        # But generally we just return existing paper.
        # If the user is owner, good. If not, do we duplicate?
        # For now, let's keep it simple: reuse existing paper.
        paper_id = cached_paper["paper_id"]
        cached_images = get_page_images(file_hash)
        if not cached_images:
            logger.info(
                f"[analyze-pdf-json] Cache HIT ({paper_id}) but images missing. Regenerating."
            )
            pdf_b64 = base64.b64encode(content).decode("utf-8")
            raw_text = None
        else:
            logger.info(f"[analyze-pdf-json] Cache HIT: paper_id={paper_id}")
            if cached_paper.get("html_content"):
                raw_text = "CACHED_HTML:" + cached_paper["html_content"]
            else:
                raw_text = cached_paper["ocr_text"]
    else:
        logger.info("[analyze-pdf-json] Cache MISS: Deferring OCR to stream")
        pdf_b64 = base64.b64encode(content).decode("utf-8")
        raw_text = None

    task_id = str(uuid.uuid4())

    # Save session context immediately if using existing paper
    if session_id and paper_id and paper_id != "pending":
        try:
            storage.save_session_context(session_id, paper_id)
            logger.info(f"[analyze-pdf-json] Pre-saved session context: {session_id} -> {paper_id}")
        except Exception as e:
            logger.error(f"[analyze-pdf-json] Failed to pre-save session context: {e}")

    task_data = {
        "format": "json",  # Flag for JSON streaming
        "lang": lang,
        "session_id": session_id,
        "filename": file.filename,
        "file_hash": file_hash,
        "user_id": user_id,  # Store user_id for stream processing
    }

    if raw_text is None:
        task_data.update(
            {
                "pending_ocr": True,
                "pdf_b64": pdf_b64,
            }
        )
    else:
        task_data.update(
            {
                "text": raw_text,
                "paper_id": paper_id,
            }
        )

    redis_service.set(f"task:{task_id}", task_data, expire=3600)

    total_elapsed = time.time() - start_time
    logger.info(f"[analyze-pdf-json] Task created: {task_id}, elapsed: {total_elapsed:.2f}s")

    return JSONResponse({"task_id": task_id, "stream_url": f"/stream/{task_id}"})


@router.post("/analyze-paper/{paper_id}")
async def analyze_paper(
    paper_id: str,
    session_id: Optional[str] = Form(None),
    user: OptionalUser = None,
):
    """
    Start streaming for an already uploaded/processed paper.
    """
    paper = storage.get_paper(paper_id)
    if not paper:
        return JSONResponse({"error": "Paper not found"}, status_code=404)

    file_hash = paper.get("file_hash")
    if not file_hash:
        return JSONResponse({"error": "Paper record is corrupt (missing hash)"}, status_code=400)

    task_id = str(uuid.uuid4())
    task_data = {
        "format": "json",
        "lang": paper.get("target_language", "ja"),
        "session_id": session_id,
        "filename": paper.get("filename", "unknown.pdf"),
        "file_hash": file_hash,
        "paper_id": paper_id,
        "user_id": user.uid if user else None,
    }

    # If we already have HTML content or OCR text, we can skip reprocessing
    if paper.get("html_content"):
        task_data["text"] = "CACHED_HTML:" + paper["html_content"]
    elif paper.get("ocr_text"):
        task_data["text"] = paper["ocr_text"]
    else:
        # This shouldn't happen if it was saved correctly, but as a fallback
        return JSONResponse(
            {"error": "Paper content is missing, please re-upload"}, status_code=400
        )

    redis_service.set(f"task:{task_id}", task_data, expire=3600)

    return JSONResponse({"task_id": task_id, "stream_url": f"/stream/{task_id}"})


async def process_figure_auto_analysis(
    figure_id: str, image_url: str, label: str = "figure", target_lang: str = "ja"
):
    """
    Background task to automatically analyze and explain a figure.
    """
    from src.domain.features.figure_insight import FigureInsightService
    from src.utils import fetch_image_bytes_from_url

    try:
        image_bytes = await fetch_image_bytes_from_url(image_url)
        if image_bytes:
            insight_service = FigureInsightService()

            if label == "equation":
                from src.domain.features.figure_insight.equation_service import EquationService

                eq_service = EquationService()
                analysis = await eq_service._analyze_bbox_with_ai(
                    image_bytes, target_lang=target_lang
                )
                if analysis:
                    storage.update_figure_explanation(figure_id, analysis.explanation)
                    storage.update_figure_latex(figure_id, analysis.latex)
            else:
                explanation = await insight_service.analyze_figure(
                    image_bytes, caption="Figure from paper", target_lang=target_lang
                )
                storage.update_figure_explanation(figure_id, explanation)

            logger.info(f"[Auto-Explain] Completed for {label} {figure_id}")
    except Exception as e:
        logger.error(f"[Auto-Explain] Failed for {label} {figure_id}: {e}")


@router.get("/stream/{task_id}")
async def stream(task_id: str):
    import json
    import time

    stream_start = time.time()
    logger.info(f"[stream] START: task_id={task_id}")

    data = redis_service.get(f"task:{task_id}")

    # Task not found
    if not data:
        return Response(status_code=204)

    is_json = data.get("format") == "json"
    text = data.get("text", "")
    paper_id = data.get("paper_id")
    lang = data.get("lang", "ja")
    session_id = data.get("session_id")
    user_id = data.get("user_id")  # Retrieve user_id

    # --- JSON STREAMING HANDLER ---
    if is_json:

        async def _inner_json_generate():
            if data.get("pending_ocr"):
                import base64

                import uuid6

                pdf_b64 = data.get("pdf_b64", "")
                filename = data.get("filename", "unknown.pdf")
                file_hash = data.get("file_hash", "")
                pdf_content = base64.b64decode(pdf_b64)

                full_text_fragments = []
                all_layout_data = []

                # User plan lookup
                user_plan = "free"
                if user_id:
                    user_data = storage.get_user(user_id)
                    if user_data:
                        user_plan = user_data.get("plan", "free")

                logger.info(f"[stream] {task_id}: Starting OCR extraction for {filename}")

                # Collect figures to save later
                collected_figures = []

                page_count = 0
                async for (
                    page_num,
                    total_pages,
                    page_text,
                    is_last,
                    f_hash,
                    page_image_url,
                    layout_data,
                ) in service.ocr_service.extract_text_streaming(
                    pdf_content, filename, user_plan=user_plan
                ):
                    page_count += 1
                    if page_text and page_text.startswith("ERROR_API_FAILED:"):
                        error_msg = page_text.replace("ERROR_API_FAILED: ", "")
                        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                        yield "event: close\ndata: done\n\n"
                        return

                    # Prepare Page Data
                    page_payload = {
                        "page_num": page_num,
                        "image_url": page_image_url,
                        "width": 0,
                        "height": 0,
                        "words": [],
                        "figures": [],
                        "content": "",
                    }

                    if page_text is not None:
                        page_payload["content"] = page_text
                        full_text_fragments.append(page_text)

                        if layout_data:
                            page_payload["width"] = layout_data["width"]
                            page_payload["height"] = layout_data["height"]
                            page_payload["words"] = layout_data.get("words", [])
                            page_payload["figures"] = layout_data.get("figures", [])

                            # Collect figures if present
                            if "figures" in layout_data:
                                collected_figures.extend(layout_data["figures"])

                            all_layout_data.append(layout_data)
                        else:
                            all_layout_data.append(None)

                    yield f"event: message\ndata: {json.dumps({'type': 'page', 'data': page_payload})}\n\n"
                    await asyncio.sleep(0.01)

                # End of OCR
                logger.info(f"[stream] {task_id}: OCR complete. Pages processed: {page_count}")
                full_text = "\n\n---\n\n".join(full_text_fragments)
                new_paper_id = str(uuid6.uuid7())

                # Save to DB (Background or here)
                try:
                    storage.save_paper(
                        paper_id=new_paper_id,
                        file_hash=file_hash,
                        filename=filename,
                        ocr_text=full_text,
                        html_content="",
                        target_language="ja",
                        layout_json=json.dumps(all_layout_data),
                        owner_id=user_id,  # Pass owner_id
                    )

                    # Save Collected Figures and Trigger Auto-Explanation
                    if collected_figures:
                        from src.crud import save_figure_to_db

                        logger.info(
                            f"Saving {len(collected_figures)} extracted figures for paper {new_paper_id}"
                        )
                        for fig in collected_figures:
                            fid = save_figure_to_db(
                                paper_id=new_paper_id,
                                page_number=fig["page_num"],
                                bbox=fig["bbox"],
                                image_url=fig["image_url"],
                                caption="",  # Can't easily extract yet
                                explanation="",  # Initially empty
                                label=fig.get("label", "figure"),
                                latex=fig.get("latex", ""),
                            )
                            # Trigger figure analysis via Cloud Tasks if enabled
                            if cloud_tasks_service.is_enabled:
                                cloud_tasks_service.enqueue_figure_analysis(fid, fig["image_url"])

                except Exception as e:
                    logger.error(f"Failed to save paper: {e}")

                # セッションコンテキスト保存 (Summary等のために必要)
                s_id = session_id or new_paper_id
                res = redis_service.set(f"session:{s_id}", full_text, expire=86400)

                # DBにもセッションマッピングを保存 (再起動対策)
                if s_id:
                    storage.save_session_context(s_id, new_paper_id)

                # --- Auto-Summarization for Abstract ---
                if cloud_tasks_service.is_enabled:
                    cloud_tasks_service.enqueue_paper_summary(new_paper_id, lang=lang)
                else:
                    try:
                        summary_full = await summary_service.summarize_full(
                            target_lang=lang, pdf_bytes=pdf_content
                        )
                        if summary_full:
                            storage.update_paper_abstract(new_paper_id, summary_full)
                            logger.info(f"Full summary saved as abstract for paper {new_paper_id}")

                    except Exception as e:
                        logger.error(f"Auto-summary generation failed: {e}")

                logger.info(
                    f"Saved session context for: {s_id} (result: {res}, length: {len(full_text)})"
                )

                yield f"event: message\ndata: {json.dumps({'type': 'done', 'paper_id': new_paper_id})}\n\n"
                await asyncio.sleep(0.01)

            else:
                # Cached content
                from ..providers.image_storage import get_page_images

                paper_data = storage.get_paper(paper_id)
                layout_list = []
                pages_text = []
                if paper_data:
                    if paper_data.get("layout_json"):
                        try:
                            layout_list = json.loads(paper_data["layout_json"])
                        except Exception as e:
                            logger.error(f"Failed to parse layout_json: {e}")
                    if paper_data.get("ocr_text"):
                        pages_text = paper_data["ocr_text"].split("\n\n---\n\n")

                f_hash = data.get("file_hash")
                logger.info(
                    f"[stream] {task_id}: Cache path for paper_id={paper_id}, f_hash={f_hash}"
                )
                if f_hash:
                    cached_images = get_page_images(f_hash)
                    logger.info(f"[stream] {task_id}: Found {len(cached_images)} cached images")
                    for i, img_url in enumerate(cached_images):
                        page_payload = {
                            "page_num": i + 1,
                            "image_url": img_url,
                            "width": 0,
                            "height": 0,
                            "words": [],
                            "figures": [],
                            "content": pages_text[i] if i < len(pages_text) else "",
                        }
                        if len(layout_list) > i and layout_list[i]:
                            page_payload["width"] = layout_list[i].get("width", 0)
                            page_payload["height"] = layout_list[i].get("height", 0)
                            page_payload["words"] = layout_list[i].get("words", [])
                            page_payload["figures"] = layout_list[i].get("figures", [])

                        yield f"event: message\ndata: {json.dumps({'type': 'page', 'data': page_payload})}\n\n"
                        await asyncio.sleep(0.01)

                # キャッシュ時もセッションコンテキストを保存（Summary等のため）
                s_id = session_id or paper_id
                if s_id and paper_data and paper_data.get("ocr_text"):
                    res = redis_service.set(f"session:{s_id}", paper_data["ocr_text"], expire=86400)
                    # DBにも保存
                    storage.save_session_context(s_id, paper_id)
                    logger.info(f"Restored session context for: {s_id} (result: {res})")
                else:
                    logger.warning(
                        f"Failed to restore session context: session_id={session_id}, paper_data={paper_data is not None}"
                    )

                yield f"event: message\ndata: {json.dumps({'type': 'done', 'paper_id': paper_id, 'cached': True})}\n\n"
                await asyncio.sleep(0.01)

            logger.info(f"[stream] {task_id}: json_generate finished")
            # Cleanup handled by wrapper

        async def json_generate():
            try:
                async for item in _inner_json_generate():
                    yield item
            except Exception as e:
                logger.error(f"[stream] {task_id}: Unexpected error in stream: {e}", exc_info=True)
                yield f"event: message\ndata: {json.dumps({'type': 'error', 'message': 'Internal Server Error'})}\n\n"
                yield "event: close\ndata: done\n\n"
            except BaseException as e:
                logger.error(
                    f"[stream] {task_id}: Critical failures (BaseException): {type(e).__name__}: {e}",
                    exc_info=True,
                )
                # Re-raise to ensure proper shutdown if it's a system exit or cancellation
                raise e
            finally:
                redis_service.delete(f"task:{task_id}")
                logger.info(f"[stream] {task_id}: Cleaned up task")

        return StreamingResponse(json_generate(), media_type="text/event-stream")

    # --- LEGACY HTML STREAMING HANDLER (Original Code) ---
    logger.info(
        f"[stream] Task data retrieved: paper_id={paper_id}, text_length={len(text)}, lang={lang}"
    )

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
            collected_figures = []

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
                if page_text and page_text.startswith("ERROR_API_FAILED:"):
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

                # Collect figures for HTMX flow
                if layout_data and "figures" in layout_data:
                    collected_figures.extend(layout_data["figures"])

                # ページコンテナID
                page_container_id = f"page-{page_num}"
                content_id = f"content-{page_container_id}"

                # 1. 部分更新（初回：画像のみ）の処理
                if page_text is None:
                    # 初回（1ページ目）はローディング表示をクリア
                    if page_num == 1:
                        yield 'event: message\ndata: <div id="paper-content" hx-swap-oob="innerHTML"></div>\n\n'

                    # コンテナ作成（画像のみ）
                    save_page_btn = f' <button onclick="saveWordToNote(\'Page {page_num}\', \'Saved from {filename}\', \'{page_image_url}\')" title="Save page to Note" class="p-1 hover:bg-white rounded transition-all opacity-50 hover:opacity-100"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>'
                    yield f'event: message\ndata: <div id="{page_container_id}" hx-swap-oob="beforeend:#paper-content" class="mb-10 bg-white shadow-sm rounded-2xl animate-fade-in overflow-hidden max-w-6xl mx-auto"><div class="flex justify-between items-center px-6 py-4 border-b border-slate-100 bg-slate-50/50"><div class="flex items-center gap-2"><span class="text-xs text-slate-400 font-bold uppercase tracking-wide">Page {page_num}/{total_pages}</span>{save_page_btn}</div><span class="text-[10px] text-slate-400 bg-slate-50 px-2 py-0.5 rounded-full font-medium italic">Loading text...</span></div><div class="relative w-full"><img src="{page_image_url}" alt="Page {page_num}" class="w-full h-auto block select-none" loading="lazy"></div></div>\n\n'
                    continue

                # 2. 完全更新（2回目：テキスト・オーバーレイ付）
                # レイアウトデータがある場合は「PDFそのまま表示モード」
                if layout_data and page_image_url:
                    img_w = layout_data["width"]
                    img_h = layout_data["height"]
                    words_html = []

                    for j, w in enumerate(layout_data["words"]):
                        bbox = w["bbox"]
                        # パーセント計算
                        left = (bbox[0] / img_w) * 100
                        top = (bbox[1] / img_h) * 100
                        width = ((bbox[2] - bbox[0]) / img_w) * 100
                        height = ((bbox[3] - bbox[1]) / img_h) * 100
                        word_text = w["word"]
                        word_id = f"w-{page_num}-{j}"

                        # 透明なクリック領域を作成
                        words_html.append(
                            f'<a id="{word_id}" class="absolute cursor-pointer hover:bg-yellow-300/30 transition-colors rounded-sm group"'
                            f' style="left:{left}%; top:{top}%; width:{width}%; height:{height}%;"'
                            f' hx-get="/explain/{word_text}?lang={lang}&element_id={word_id}"'
                            f' hx-trigger="click"'
                            f' hx-target="#definition-box"'
                            f' hx-swap="afterbegin">'
                            f"</a>"
                        )

                    full_words_html = "".join(words_html)

                    # コンテナ全体を置換 (hx-swap-oob="outerHTML")
                    save_page_btn = f' <button onclick="saveWordToNote(\'Page {page_num}\', \'Saved from {filename}\', \'{page_image_url}\')" title="Save page to Note" class="p-1 hover:bg-white rounded transition-all opacity-50 hover:opacity-100"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>'
                    yield f'event: message\ndata: <div id="{page_container_id}" hx-swap-oob="outerHTML" class="mb-10 bg-white shadow-sm rounded-2xl animate-fade-in overflow-hidden max-w-6xl mx-auto"><div class="flex justify-between items-center px-6 py-4 border-b border-slate-100 bg-slate-50/50"><div class="flex items-center gap-2"><span class="text-xs text-slate-400 font-bold uppercase tracking-wide">Page {page_num}/{total_pages}</span>{save_page_btn}</div><span class="text-[10px] text-indigo-500 bg-indigo-50 px-2 py-0.5 rounded-full font-medium">Interactive PDF</span></div><div class="relative w-full"><img src="{page_image_url}" alt="Page {page_num}" class="w-full h-auto block select-none" loading="lazy"><div class="absolute inset-0 w-full h-full">{full_words_html}</div></div></div>\n\n'

                # レイアウトデータがない場合（OCRフォールバック）
                else:
                    save_page_btn = f' <button onclick="saveWordToNote(\'Page {page_num} OCR\', \'Saved from {filename}\', \'{page_image_url}\')" title="Save page to Note" class="p-1 hover:bg-white rounded transition-all opacity-50 hover:opacity-100"><svg class="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4" /></svg></button>'
                    yield f'event: message\ndata: <div id="{page_container_id}" hx-swap-oob="outerHTML" class="mb-10 bg-white shadow-sm rounded-2xl animate-fade-in overflow-hidden"><div class="flex justify-between items-center px-6 py-4 border-b border-slate-100 bg-slate-50/50"><div class="flex items-center gap-2"><span class="text-xs text-slate-400 font-bold uppercase tracking-wide">Page {page_num}/{total_pages}</span>{save_page_btn}</div><span class="text-[10px] text-green-500 bg-green-50 px-2 py-0.5 rounded-full font-medium">Ready</span></div><div class="grid grid-cols-1 lg:grid-cols-2 gap-0"><div class="p-4 bg-slate-50 border-r border-slate-100 flex items-start justify-center"><img src="{page_image_url}" alt="Page {page_num}" class="max-w-full h-auto rounded-lg shadow-sm border border-slate-200" loading="lazy"></div><div id="{content_id}" class="p-6 overflow-y-auto max-h-[800px]"></div></div></div>\n\n'

                    # テキストトークン化ストリーム
                    page_prefix = f"p-pg{page_num}"
                    async for chunk in service.tokenize_stream(
                        page_text,
                        paper_id=None,
                        target_id=content_id,
                        id_prefix=page_prefix,
                        save_to_db=False,
                        lang=lang,
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

                # Save Collected Figures and Explain
                if collected_figures:
                    from src.crud import save_figure_to_db

                    logger.info(
                        f"Saving {len(collected_figures)} extracted figures for paper {paper_id}"
                    )
                    for fig in collected_figures:
                        fid = save_figure_to_db(
                            paper_id=paper_id,
                            page_number=fig["page_num"],
                            bbox=fig["bbox"],
                            image_url=fig["image_url"],
                            caption="",
                            explanation="",
                            label=fig.get("label", "figure"),
                            latex=fig.get("latex", ""),
                        )
                        if cloud_tasks_service.is_enabled:
                            cloud_tasks_service.enqueue_figure_analysis(fid, fig["image_url"])

            except Exception as e:
                logger.error(f"Failed to save paper: {e}")

            # セッションコンテキスト保存
            if session_id:
                redis_service.set(f"session:{session_id}", full_text, expire=86400)
                # DBにも保存
                storage.save_session_context(session_id, paper_id)

            # --- Auto-Summarization for Abstract ---
            if cloud_tasks_service.is_enabled:
                cloud_tasks_service.enqueue_paper_summary(paper_id, lang=lang)
            else:
                try:
                    summary_full = await summary_service.summarize_full(
                        target_lang=lang, pdf_bytes=pdf_content
                    )
                    if summary_full:
                        storage.update_paper_abstract(paper_id, summary_full)
                        logger.info(f"Full summary saved as abstract for paper {paper_id}")
                except Exception as e:
                    logger.error(f"Auto-summary generation failed: {e}")

            # 完了処理

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
        async for chunk in service.tokenize_stream(text, paper_id, lang=lang):
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
