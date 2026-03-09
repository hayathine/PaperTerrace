"""
PDF Analysis & OCR Router
Handles PDF upload, OCR processing, and streaming text analysis.
"""

import asyncio
import os
import uuid

from fastapi import APIRouter, BackgroundTasks, File, Form, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse

from app.auth import OptionalUser
from app.core.config import is_production
from app.domain.features import SummaryService
from app.domain.services.analysis_service import EnglishAnalysisService
from app.domain.services.paper_processing import (
    process_figure_analysis_task,
    process_paper_summary_task,
)
from app.providers import (
    RedisService,
    get_image_storage,
    get_storage_provider,
)
from app.utils import _get_file_hash
from common.logger import ServiceLogger

log = ServiceLogger("PDF")


router = APIRouter(tags=["PDF Analysis"])

# Services


# Services
service = EnglishAnalysisService()
summary_service = SummaryService()
storage = get_storage_provider()
redis_service = RedisService()
img_storage = get_image_storage()


@router.post("/session-context")
async def update_session_context(
    session_id: str = Form(...),
    paper_id: str = Form(...),
):
    """セッション→論文マッピングを更新する（キャッシュ表示時用）。"""
    try:
        storage.save_session_context(session_id, paper_id)
        # Redis のセッションコンテキストも更新
        paper = storage.get_paper(paper_id)
        if paper and paper.get("ocr_text"):
            redis_service.set(f"session:{session_id}", paper["ocr_text"], expire=3600)
        log.info(
            "session_context",
            "Session context updated",
            session_id=session_id,
            paper_id=paper_id,
        )
        return JSONResponse({"ok": True})
    except Exception as e:
        log.warning(
            "session_context",
            "Failed to update session context",
            session_id=session_id,
            paper_id=paper_id,
            error=str(e),
        )
        return JSONResponse({"ok": False}, status_code=500)


@router.post("/analyze-pdf")
async def analyze_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    session_id: str | None = Form(None),
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
    detected_lang = await service.ocr_service.language_service.detect_language(content)
    if detected_lang and detected_lang != "en":
        log.warning("analyze", "Unsupported language detected", lang=detected_lang)
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

    if cached_paper:
        paper_id = cached_paper["paper_id"]
        if cached_paper.get("ocr_text"):
            raw_text = cached_paper["ocr_text"]

    # Check if user is registered (exists in our DB)
    is_registered = False
    if user_id:
        try:
            if storage.get_user(user_id):
                is_registered = True
        except Exception:
            pass

    task_id = str(uuid.uuid4())

    task_data = {
        "format": "html",  # Default for HTMX
        "lang": lang,
        "session_id": session_id,
        "filename": file.filename,
        "file_hash": file_hash,
        "user_id": user_id,
        "is_registered": is_registered,
        "paper_id": paper_id,
    }

    if raw_text is None:
        doc_path = img_storage.save_doc(file_hash, content)
        task_data.update({"pending_ocr": True, "pdf_path": doc_path})
    else:
        task_data.update({"text": raw_text})

    redis_service.set(f"task:{task_id}", task_data, expire=3600)  # 1-hour session

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
    session_id: str | None = Form(None),
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
    log.info("analyze_json", "START", filename=file.filename, size=file.size)

    # Capture user_id
    user_id = user.uid if user else None
    if user_id:
        log.info("analyze_json", "Authenticated user", user_id=user_id)

    content = await file.read()
    file_hash = _get_file_hash(content)
    log.info(
        "analyze_json", "Input received", session_id=session_id, file_hash=file_hash
    )

    # Detect PDF language
    try:
        detected_lang = await service.ocr_service.language_service.detect_language(
            content
        )
        if detected_lang and detected_lang != "en":
            log.warning(
                "analyze_json", f"Unsupported language detected: {detected_lang}"
            )
            return JSONResponse(
                {
                    "error": "Currently, only English papers are supported. / 現在、英語の論文のみサポートしています。"
                },
                status_code=400,
            )
        if detected_lang:
            lang = detected_lang

        # Cache check
        cached_paper = storage.get_paper_by_hash(file_hash)
        raw_text = None

        if cached_paper:
            paper_id = cached_paper["paper_id"]
            # Safe image check + regeneration logic
            try:
                from app.providers.image_storage import get_page_images

                cached_images = get_page_images(file_hash)
            except ImportError as ie:
                log.error(
                    "analyze_json", "Failed to import get_page_images", error=str(ie)
                )
                cached_images = []

            if not cached_images:
                log.info(
                    "analyze_json",
                    "Cache HIT but images missing. Regenerating.",
                    paper_id=paper_id,
                )
                raw_text = None
            else:
                storage_type = os.getenv("STORAGE_TYPE", "local").upper()
                log.info(
                    "analyze_json",
                    "Cache HIT",
                    storage_type=storage_type,
                    paper_id=paper_id,
                )

                if cached_paper.get("html_content"):
                    raw_text = "CACHED_HTML:" + cached_paper["html_content"]
                else:
                    raw_text = cached_paper.get("ocr_text")
        else:
            import uuid6

            paper_id = str(uuid6.uuid7())
            log.info("analyze_json", "Cache MISS", paper_id=paper_id)
            raw_text = None

        # Check if user is registered (exists in our DB)
        is_registered = False
        if user_id:
            try:
                if storage.get_user(user_id):
                    is_registered = True
                    log.info("analyze_json", "User is registered", user_id=user_id)
                else:
                    log.info(
                        "analyze_json", "User is a guest (not in DB)", user_id=user_id
                    )

            except Exception as e:
                log.error(
                    "analyze_json", "Failed to check user registration", error=str(e)
                )

        task_id = str(uuid.uuid4())

        # Save session context immediately if using existing paper AND registered
        if is_registered and session_id and paper_id and paper_id != "pending":
            try:
                storage.save_session_context(session_id, paper_id)
                log.info(
                    "analyze_json",
                    "Pre-saved session context",
                    session_id=session_id,
                    paper_id=paper_id,
                )

            except Exception as e:
                log.error(
                    "analyze_json", "Failed to pre-save session context", error=str(e)
                )

        task_data = {
            "format": "json",  # Flag for JSON streaming
            "lang": lang,
            "session_id": session_id,
            "filename": file.filename,
            "file_hash": file_hash,
            "user_id": user_id,  # Store user_id for stream processing
            "is_registered": is_registered,
            "paper_id": paper_id,
        }

        if raw_text is None:
            # Save PDF to disk instead of Redis to prevent OOM
            doc_path = img_storage.save_doc(file_hash, content)
            task_data.update(
                {
                    "pending_ocr": True,
                    "pdf_path": doc_path,
                }
            )
        else:
            task_data.update(
                {
                    "text": raw_text,
                }
            )

        # Set 1-hour sliding expiration for paper sessions (3600s)
        redis_service.set(f"task:{task_id}", task_data, expire=3600)

        total_elapsed = time.time() - start_time
        log.info(
            "analyze_json",
            "Task created",
            task_id=task_id,
            elapsed=f"{total_elapsed:.2f}s",
        )

        return JSONResponse(
            {"task_id": task_id, "stream_url": f"/api/stream/{task_id}"}
        )

    except Exception as e:
        log.error("analyze_json", "Unexpected error", error=str(e), exc_info=True)

        error_msg = (
            str(e)
            if not is_production()
            else "An error occurred while analyzing the document."
        )
        return JSONResponse({"error": error_msg}, status_code=500)


@router.post("/analyze-paper/{paper_id}")
async def analyze_paper(
    paper_id: str,
    session_id: str | None = Form(None),
    user: OptionalUser = None,
):
    """
    Start streaming for an already uploaded/processed paper.
    """
    try:
        paper = storage.get_paper(paper_id)
        if not paper:
            return JSONResponse({"error": "Paper not found"}, status_code=404)

        file_hash = paper.get("file_hash")
        if not file_hash:
            return JSONResponse(
                {"error": "Paper record is corrupt (missing hash)"}, status_code=400
            )

        user_id = user.uid if user else None
        is_registered = False
        if user_id:
            try:
                if storage.get_user(user_id):
                    is_registered = True
            except Exception:
                pass

        task_id = str(uuid.uuid4())
        task_data = {
            "format": "json",
            "lang": paper.get("target_language", "ja"),
            "session_id": session_id,
            "filename": paper.get("filename", "unknown.pdf"),
            "file_hash": file_hash,
            "paper_id": paper_id,
            "user_id": user_id,
            "is_registered": is_registered,
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

        redis_service.set(f"task:{task_id}", task_data, expire=3600)  # 1-hour session

        return JSONResponse(
            {"task_id": task_id, "stream_url": f"/api/stream/{task_id}"}
        )
    except Exception as e:
        log.error(
            "analyze_paper",
            "Error starting paper analysis",
            error=str(e),
            paper_id=paper_id,
        )
        error_msg = (
            str(e)
            if not is_production()
            else "An error occurred while analyzing the document."
        )
        return JSONResponse({"error": error_msg}, status_code=500)


@router.get("/stream/{task_id}")
async def stream(task_id: str):
    import json
    import time

    stream_start = time.time()
    log.info("stream", "START", task_id=task_id)

    data = redis_service.get(f"task:{task_id}")
    if data:
        # Refresh task TTL on access
        redis_service.expire(f"task:{task_id}", 3600)

    # Task not found - return proper error response instead of 204
    if not data:
        log.warning("stream", "Task not found", task_id=task_id)

        return Response(
            content=f"data: {json.dumps({'type': 'error', 'message': 'Task not found or expired'})}\n\n",
            media_type="text/plain",
            status_code=200,
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    is_json = data.get("format") == "json"
    text = data.get("text", "")
    paper_id = data.get("paper_id")
    lang = data.get("lang", "ja")
    session_id = data.get("session_id")
    user_id = data.get("user_id")  # Retrieve user_id
    file_hash = data.get("file_hash", "")
    filename = data.get("filename", "unknown.pdf")

    # --- JSON STREAMING HANDLER ---
    if is_json:

        async def _inner_json_generate():
            if data.get("pending_ocr"):
                pdf_path = data.get("pdf_path")
                pdf_b64 = data.get("pdf_b64", "")

                if pdf_path:
                    try:
                        pdf_content = img_storage.get_doc_bytes(pdf_path)
                    except Exception as e:
                        log.error(
                            "stream",
                            f"Failed to read PDF from {pdf_path}: {e}",
                            task_id=task_id,
                            pdf_path=pdf_path,
                        )

                        yield f"data: {json.dumps({'type': 'error', 'message': 'PDF source not found or inaccessible'})}\n\n"
                        return
                elif pdf_b64:
                    import base64

                    pdf_content = base64.b64decode(pdf_b64)
                else:
                    log.error("stream", "No PDF source found", task_id=task_id)

                    yield f"data: {json.dumps({'type': 'error', 'message': 'PDF source not found'})}\n\n"
                    return

                full_text_fragments = []
                all_layout_data = []

                # User plan lookup
                user_plan = "free"
                if user_id:
                    user_data = storage.get_user(user_id)
                    if user_data:
                        user_plan = user_data.get("plan", "free")

                log.info(
                    "stream",
                    "Starting OCR extraction",
                    task_id=task_id,
                    filename=filename,
                )

                # Collect figures to save later
                collected_figures = []

                page_count = 0
                async for result_tuple in service.ocr_service.extract_text_streaming(
                    pdf_content, filename, user_plan=user_plan
                ):
                    if len(result_tuple) != 7:
                        log.error(
                            "stream",
                            f"UNEXPECTED TUPLE LENGTH: {len(result_tuple)} - {result_tuple}",
                            task_id=task_id,
                        )
                        continue

                    (
                        page_num,
                        total_pages,
                        page_text,
                        is_last,
                        f_hash,
                        page_image_url,
                        layout_data,
                    ) = result_tuple
                    page_count += 1
                    if page_text and page_text.startswith("ERROR_API_FAILED:"):
                        error_msg = page_text.replace("ERROR_API_FAILED: ", "")
                        yield f"data: {json.dumps({'type': 'error', 'message': error_msg})}\n\n"
                        yield "event: close\ndata: done\n\n"
                        return

                    # Skip phase 1 (text only) to prevent frontend crash due to null image_url
                    if not page_image_url:
                        continue

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

                            # Debug: Log what we're sending to frontend

                            # Collect figures if present
                            if "figures" in layout_data:
                                collected_figures.extend(layout_data["figures"])

                            all_layout_data.append(layout_data)
                        else:
                            log.warning(
                                "stream",
                                f"Page {page_num} has no layout_data!",
                                task_id=task_id,
                                page_num=page_num,
                            )

                            all_layout_data.append(None)

                    yield f"event: message\ndata: {json.dumps({'type': 'page', 'data': page_payload})}\n\n"
                    await asyncio.sleep(0.01)

                # End of OCR

                # Send coordinates ready event (Phase 2 completion)
                yield f"event: message\ndata: {json.dumps({'type': 'coordinates_ready', 'page_count': page_count})}\n\n"
                await asyncio.sleep(0.01)

                # Send assist mode ready event
                yield f"event: message\ndata: {json.dumps({'type': 'assist_mode_ready'})}\n\n"
                await asyncio.sleep(0.01)

                full_text = "\n\n---\n\n".join(full_text_fragments)
                # paper_id is now pre-generated and passed in task data
                new_paper_id = paper_id

                # Save to permanent DB ONLY for registered users (prevent DB clutter for transient guest sessions)
                # Transient sessions rely on Redis and Frontend IndexedDB.
                if user_id:
                    try:
                        from app.crud import save_figure_to_db
                        from app.domain.services.paper_processing import (
                            process_figure_analysis_task,
                            process_paper_summary_task,
                        )

                        storage.save_paper(
                            paper_id=new_paper_id,
                            file_hash=file_hash,
                            filename=filename,
                            ocr_text=full_text,
                            html_content="",
                            target_language="ja",
                            layout_json=json.dumps(all_layout_data),
                            owner_id=user_id,
                        )
                        # DBにもセッションマッピングを保存
                        if session_id:
                            storage.save_session_context(session_id, new_paper_id)

                        log.info(
                            "stream",
                            f"Paper saved to DB for user {user_id}",
                            task_id=task_id,
                            user_id=user_id,
                            paper_id=new_paper_id,
                        )

                        # Trigger background tasks (require DB records)
                        asyncio.create_task(
                            process_paper_summary_task(new_paper_id, lang=lang)
                        )

                        # Save figure metadata for each page
                        # The original code iterated collected_figures, which was a flat list.
                        # The new code iterates all_layout_data and then figures within each page.
                        # To maintain consistency with the original's collected_figures logic,
                        # we'll use collected_figures here.
                        if collected_figures:
                            for fig in collected_figures:
                                fid = save_figure_to_db(
                                    paper_id=new_paper_id,
                                    page_number=fig[
                                        "page_num"
                                    ],  # Use page_num from collected_figures
                                    bbox=fig.get("bbox", []),
                                    image_url=fig.get("image_url", ""),
                                    label=fig.get("label", "figure"),
                                    latex=fig.get("latex", ""),  # Keep latex if present
                                )
                                # Optional: Trigger detailed figure analysis in background
                                asyncio.create_task(
                                    process_figure_analysis_task(
                                        fid, fig.get("image_url", "")
                                    )
                                )
                    except Exception as db_err:
                        log.error(
                            "stream",
                            f"Failed to save to DB: {db_err}",
                            task_id=task_id,
                            paper_id=new_paper_id,
                        )

                else:
                    log.info(
                        "stream",
                        "Skipping DB save for guest/transient session",
                        task_id=task_id,
                    )

                # Redis session context (1-hour sliding limit, TRUNCATED to 20k chars to prevent OOM)
                s_id = session_id or new_paper_id
                # Store only the first 20,000 characters in Redis as "recent context"
                recent_context = full_text[:20000]
                redis_service.set(f"session:{s_id}", recent_context, expire=3600)

                yield f"event: message\ndata: {json.dumps({'type': 'done', 'paper_id': new_paper_id})}\n\n"
                await asyncio.sleep(0.01)

            else:
                # Cached content
                from app.providers.image_storage import get_page_images

                paper_data = storage.get_paper(paper_id)
                layout_list = []
                pages_text = []
                if paper_data:
                    if paper_data.get("layout_json"):
                        try:
                            layout_list = json.loads(paper_data["layout_json"])
                            log.debug(
                                "stream",
                                "Loaded layout_list from DB",
                                task_id=task_id,
                                pages=len(layout_list),
                            )
                        except Exception as e:
                            log.error(
                                "stream",
                                f"Failed to parse layout_json: {e}",
                                task_id=task_id,
                            )

                    else:
                        log.warning(
                            "stream",
                            "No layout_json in paper_data!",
                            task_id=task_id,
                        )

                    if paper_data.get("ocr_text"):
                        pages_text = paper_data["ocr_text"].split("\n\n---\n\n")

                f_hash = data.get("file_hash")
                log.info(
                    "stream",
                    "Cache path for paper",
                    task_id=task_id,
                    paper_id=paper_id,
                    f_hash=f_hash,
                )

                if f_hash:
                    cached_images = get_page_images(f_hash)
                    log.info(
                        "stream",
                        "Found cached images",
                        task_id=task_id,
                        count=len(cached_images),
                    )

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

                            log.debug(
                                "stream",
                                f"Page {i + 1} loaded from cache",
                                task_id=task_id,
                                page_num=i + 1,
                                words=len(page_payload["words"]),
                                width=page_payload["width"],
                                height=page_payload["height"],
                            )

                        else:
                            log.warning(
                                "stream",
                                f"Page {i + 1} missing from layout_list!",
                                task_id=task_id,
                                page_num=i + 1,
                                layout_list_len=len(layout_list),
                            )

                        yield f"event: message\ndata: {json.dumps({'type': 'page', 'data': page_payload})}\n\n"
                        await asyncio.sleep(0.01)

                    # キャッシュされたデータの場合、座標は既に準備済み
                    yield f"event: message\ndata: {json.dumps({'type': 'coordinates_ready', 'page_count': len(cached_images)})}\n\n"
                    await asyncio.sleep(0.01)

                    # キャッシュされたデータの場合もassist_mode_readyイベントを送信
                    yield f"event: message\ndata: {json.dumps({'type': 'assist_mode_ready'})}\n\n"
                    await asyncio.sleep(0.01)

                # キャッシュ時もセッションコンテキストを保存（Summary等のため）
                s_id = session_id or paper_id
                if s_id and paper_data and paper_data.get("ocr_text"):
                    redis_service.set(
                        f"session:{s_id}", paper_data["ocr_text"], expire=3600
                    )  # Align TTL to 1 hour
                    log.info(
                        "stream",
                        "Restored session context",
                        s_id=s_id,
                    )

                # DBのセッション→論文マッピングも更新（レビュー等が正しい論文を参照するため）
                if session_id and paper_id:
                    try:
                        storage.save_session_context(session_id, paper_id)
                    except Exception as e:
                        log.warning(
                            "stream",
                            "Failed to save session context for cached paper",
                            session_id=session_id,
                            paper_id=paper_id,
                            error=str(e),
                        )

                else:
                    log.warning(
                        "stream",
                        "Failed to restore session context",
                        session_id=session_id,
                        has_paper_data=paper_data is not None,
                    )

                yield f"event: message\ndata: {json.dumps({'type': 'done', 'paper_id': paper_id, 'cached': True})}\n\n"
                await asyncio.sleep(0.01)

            log.info("stream", "json_generate finished", task_id=task_id)

            # Cleanup handled by wrapper

        async def json_generate():
            try:
                async for item in _inner_json_generate():
                    yield item
            except asyncio.CancelledError:
                # Client disconnected - this is normal, log at info level
                log.info(
                    "stream", "Client disconnected (CancelledError)", task_id=task_id
                )

                # Don't delete task immediately - keep it for potential reconnection

            except Exception as e:
                log.error(
                    "stream",
                    f"Unexpected error in stream: {e}",
                    task_id=task_id,
                    exc_info=True,
                )

                try:
                    yield f"event: message\ndata: {json.dumps({'type': 'error', 'message': 'Internal Server Error'})}\n\n"
                    yield "event: close\ndata: done\n\n"
                except Exception:
                    pass  # Client may already be disconnected
                # Delete task only on actual errors, not client disconnects
                redis_service.delete(f"task:{task_id}")
                log.info("stream", "Cleaned up task due to error", task_id=task_id)
            else:
                # Normal completion - delete task
                redis_service.delete(f"task:{task_id}")
                log.info(
                    "stream",
                    "Cleaned up task after normal completion",
                    task_id=task_id,
                )

        return StreamingResponse(json_generate(), media_type="text/event-stream")

    # OCR未実行の場合：ストリーム内でOCR処理を行う
    if data.get("pending_ocr"):
        pdf_path = data.get("pdf_path")
        pdf_b64 = data.get("pdf_b64", "")

        if pdf_path:
            try:
                pdf_content = img_storage.get_doc_bytes(pdf_path)
            except Exception as e:
                log.error(
                    "stream", f"{task_id}: Failed to read PDF from {pdf_path}: {e}"
                )
                return Response(
                    "Error: PDF source not found or inaccessible", status_code=404
                )
        elif pdf_b64:
            import base64

            pdf_content = base64.b64decode(pdf_b64)
        else:
            return Response("Error: PDF source not found", status_code=404)

        async def ocr_generate():
            # paper_id is pre-generated in analyze_pdf or analyze_pdf_json
            nonlocal paper_id
            if not paper_id or paper_id == "pending":
                import uuid6

                paper_id = str(uuid6.uuid7())

            log.info("stream", "ocr_generate started", paper_id=paper_id)

            yield 'event: message\ndata: <div id="paper-content" hx-swap-oob="innerHTML"><div class="flex flex-col items-center justify-center min-h-[400px] text-center"><div class="animate-spin rounded-full h-12 w-12 border-4 border-indigo-200 border-t-indigo-600 mb-4"></div><p class="text-slate-500 font-medium">📄 PDFを解析中...</p><p class="text-xs text-slate-400 mt-2">AI OCRで文字認識を実行しています<br>ページごとに順次表示されます</p></div></div>\n\n'

            full_text_fragments = []
            all_layout_data = []  # Added to collect layout data
            collected_figures = []

            # ページ単位OCRストリーム
            async for result_tuple in service.ocr_service.extract_text_streaming(
                pdf_content, filename
            ):
                if len(result_tuple) != 7:
                    log.error(
                        "stream_html",
                        f"UNEXPECTED TUPLE LENGTH: {len(result_tuple)} - {result_tuple}",
                    )
                    continue
                (
                    page_num,
                    total_pages,
                    page_text,
                    is_last,
                    f_hash,
                    page_image_url,
                    layout_data,
                ) = result_tuple
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
                all_layout_data.append(layout_data)

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
                            f' hx-target="#dict-stack"'
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
                        paper_id=paper_id,
                        target_id=content_id,
                        id_prefix=page_prefix,
                        save_to_db=False,
                        lang=lang,
                    ):
                        yield chunk
                        await asyncio.sleep(0.005)

            # 全ページ完了後、DB保存 (Backup for analysis tasks)
            full_text = "\n\n---\n\n".join(full_text_fragments)

            try:
                storage.save_paper(
                    paper_id=paper_id,
                    file_hash=file_hash,
                    filename=filename,
                    ocr_text=full_text,
                    html_content="",
                    target_language="ja",
                    owner_id=user_id,
                )
                log.info("ocr_generate", "Paper record saved", paper_id=paper_id)

                # Save Collected Figures and Explain
                if collected_figures:
                    from app.crud import save_figure_to_db

                    log.info(
                        "ocr_generate",
                        f"Saving {len(collected_figures)} extracted figures",
                        paper_id=paper_id,
                    )

                    for fig in collected_figures:
                        fid = save_figure_to_db(
                            paper_id=paper_id,
                            page_number=fig["page_num"],
                            bbox=fig["bbox"],
                            image_url=fig["image_url"],
                            caption="",  # Can't easily extract yet
                            explanation="",  # Initially empty
                            label=fig.get("label", "figure"),
                            latex=fig.get("latex", ""),
                        )
                        # Trigger figure analysis via asyncio task
                        asyncio.create_task(
                            process_figure_analysis_task(fid, fig["image_url"])
                        )

                # --- Auto-Summarization for Abstract ---
                asyncio.create_task(process_paper_summary_task(paper_id, lang=lang))

                # DBにもセッションマッピングを保存
                if session_id:
                    storage.save_session_context(session_id, paper_id)

            except Exception as e:
                log.error(
                    "ocr_generate",
                    f"Failed to save paper record: {e}",
                    paper_id=paper_id,
                )

            # Redisセッションコンテキストを1時間保持 (sliding)
            if session_id:
                redis_service.set(f"session:{session_id}", full_text, expire=3600)

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
        log.info("stream", "Serving cached HTML", paper_id=paper_id)

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
            log.info(
                "cached_generate",
                "END (cached)",
                task_id=task_id,
                elapsed=f"{time.time() - stream_start:.2f}s",
            )

        redis_service.delete(f"task:{task_id}")
        return StreamingResponse(cached_generate(), media_type="text/event-stream")

    log.info("stream", "Starting tokenization", paper_id=paper_id)

    async def generate():
        async for chunk in service.tokenize_stream(text, paper_id, lang=lang):
            yield chunk
            await asyncio.sleep(0.01)

        redis_service.delete(f"task:{task_id}")
        log.info(
            "generate",
            "END",
            task_id=task_id,
            paper_id=paper_id,
            elapsed=f"{time.time() - stream_start:.2f}s",
        )

        # フロントエンドにpaper_idを通知
        yield f'event: message\ndata: <input type="hidden" id="current-paper-id" value="{paper_id}" hx-swap-oob="true" />\n\n'

        # ストリーム終了時に、SSEコンテナ自体を通常のdivに置換して接続を物理的に切断する
        yield f'event: message\ndata: <div id="sse-container-{task_id}" hx-swap-oob="outerHTML" data-paper-id="finished" style="display:none"></div>\n\n'

        # 念のためcloseイベントも送る
        yield "event: close\ndata: done\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")
