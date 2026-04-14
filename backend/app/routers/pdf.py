"""
PDF Analysis & OCR Router
Handles PDF upload, OCR processing, and streaming text analysis.
"""

import asyncio
import json
import re
import time
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

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
from app.providers.image_storage import get_upload_signed_url, pdf_blob_exists
from app.utils import _get_file_hash
from common import settings
from common.logger import ServiceLogger
from redis_provider.provider import get_is_registered

log = ServiceLogger("PDF")


router = APIRouter(tags=["PDF Analysis"])

# Services
service = EnglishAnalysisService()
summary_service = SummaryService()
redis_service = RedisService()
img_storage = get_image_storage()


@dataclass
class PdfReadResult:
    """PDF 読み込み・検証の結果を保持するデータクラス。"""

    content: bytes
    file_hash: str
    lang: str
    user_id: str | None
    is_registered: bool


async def _read_and_validate_pdf(
    file: UploadFile,
    session_id: str | None,
    user: OptionalUser,
    max_pdf_bytes: int,
) -> PdfReadResult | tuple[str, int]:
    """PDF を読み込み、サイズ・言語を検証する。

    Returns:
        PdfReadResult: 検証成功時の結果。
        tuple[str, int]: エラーメッセージとステータスコード（検証失敗時）。
    """
    if file.size and file.size > max_pdf_bytes:
        return (f"File too large. Maximum size is {max_pdf_bytes // (1024 * 1024)}MB.", 413)

    content = await file.read()
    # file.size が None（Content-Length 未送信）の場合に備え、読み込み後にもサイズを検証する
    if len(content) > max_pdf_bytes:
        return (f"File too large. Maximum size is {max_pdf_bytes // (1024 * 1024)}MB.", 413)

    file_hash = _get_file_hash(content)

    detected_lang = await service.ocr_service.language_service.detect_language(content)
    if detected_lang and detected_lang != "en":
        return (
            "Currently, only English papers are supported. / 現在、英語の論文のみサポートしています。",
            400,
        )
    lang = detected_lang or "ja"

    user_id = user.uid if user else (f"guest:{session_id}" if session_id else None)
    is_registered = get_is_registered(user_id)

    return PdfReadResult(
        content=content,
        file_hash=file_hash,
        lang=lang,
        user_id=user_id,
        is_registered=is_registered,
    )


def _resolve_cached_paper(
    file_hash: str,
    storage: object,
    log_prefix: str,
    *,
    new_id_on_missing_images: bool = False,
) -> tuple[str, str | None]:
    """DB キャッシュと画像キャッシュを確認し、paper_id と raw_text を返す。

    Args:
        file_hash: PDF ファイルのハッシュ値。
        storage: StorageInterface 実装。
        log_prefix: ログ識別子（例: "analyze_json", "analyze_hash"）。
        new_id_on_missing_images: True の場合、画像キャッシュがないとき新しい UUID を生成する。
            False（デフォルト）では既存の paper_id を保持して OCR を再トリガーする。

    Returns:
        (paper_id, raw_text): raw_text は None の場合 OCR が必要。
    """
    import uuid6

    cached_paper = storage.get_paper_by_hash(file_hash)

    if not cached_paper:
        paper_id = str(uuid6.uuid7())
        log.info(log_prefix, "キャッシュミス", paper_id=paper_id)
        return paper_id, None

    paper_id = cached_paper["paper_id"]

    try:
        from app.providers.image_storage import get_page_images

        cached_images = get_page_images(file_hash)
    except ImportError as ie:
        log.error(log_prefix, "Failed to import get_page_images", error=str(ie))
        cached_images = []

    if not cached_images:
        if new_id_on_missing_images:
            paper_id = str(uuid6.uuid7())
        log.info(
            log_prefix,
            "キャッシュはヒットしましたが画像が見つかりません。再生成します。",
            paper_id=paper_id,
        )
        return paper_id, None

    log.info(log_prefix, "キャッシュヒット", paper_id=paper_id)
    if cached_paper.get("html_content"):
        raw_text = "CACHED_HTML:" + cached_paper["html_content"]
    else:
        raw_text = cached_paper.get("ocr_text")
    return paper_id, raw_text


@router.post("/session-context")
async def update_session_context(
    session_id: str = Form(...),
    paper_id: str = Form(...),
):
    """セッション→論文マッピングを更新する（キャッシュ表示時用）。"""
    try:
        storage = get_storage_provider()
        storage.save_session_context(session_id, paper_id)
        # Redis のセッションコンテキストも更新
        paper = storage.get_paper(paper_id)
        if paper and paper.get("ocr_text"):
            redis_service.set(f"session:ctx:{session_id}", paper["ocr_text"], expire=3600)
        log.info(
            "session_context",
            "セッションコンテキストを更新しました",
            session_id=session_id,
            paper_id=paper_id,
        )
        return JSONResponse({"ok": True})
    except Exception as e:
        log.warning(
            "session_context",
            "セッションコンテキストの更新に失敗しました",
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
    """Standard HTML version of analyze-pdf for HTMX. Returns HTML with SSE connection."""
    if not file.filename or file.size == 0:
        return Response("Error: No file", status_code=400)

    max_pdf_bytes = int(settings.get("MAX_PDF_SIZE_MB", "50")) * 1024 * 1024
    validated = await _read_and_validate_pdf(file, session_id, user, max_pdf_bytes)
    if isinstance(validated, tuple):
        error_msg, status_code = validated
        return Response(f"Error: {error_msg}", status_code=status_code)

    storage = get_storage_provider()
    cached_paper = storage.get_paper_by_hash(validated.file_hash)
    raw_text = None
    paper_id = "pending"

    if cached_paper:
        paper_id = cached_paper["paper_id"]
        if cached_paper.get("ocr_text"):
            raw_text = cached_paper["ocr_text"]

    task_id = str(uuid.uuid4())
    task_data: dict = {
        "format": "html",
        "lang": validated.lang,
        "session_id": session_id,
        "filename": file.filename,
        "file_hash": validated.file_hash,
        "user_id": validated.user_id,
        "is_registered": validated.is_registered,
        "paper_id": paper_id,
    }

    if raw_text is None:
        doc_path = img_storage.save_doc(validated.file_hash, validated.content)
        task_data.update({"pending_ocr": True, "pdf_path": doc_path})
    else:
        task_data.update({"text": raw_text})

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
    session_id: str | None = Form(None),
    lang: str = Form("ja"),
    user: OptionalUser = None,
):
    """JSON version of analyze-pdf for React frontend.
    Returns { "task_id": "...", "stream_url": "/stream/..." }
    """
    if not file.filename or file.size == 0:
        return JSONResponse({"error": "No file provided"}, status_code=400)

    max_pdf_bytes = int(settings.get("MAX_PDF_SIZE_MB", "50")) * 1024 * 1024
    storage = get_storage_provider()
    start_time = time.time()
    log.info("analyze_json", "開始", filename=file.filename, size=file.size)

    validated = await _read_and_validate_pdf(file, session_id, user, max_pdf_bytes)
    if isinstance(validated, tuple):
        error_msg, status_code = validated
        return JSONResponse({"error": error_msg}, status_code=status_code)

    log.info(
        "analyze_json",
        "入力を受け取リました",
        session_id=session_id,
        file_hash=validated.file_hash,
    )
    if validated.user_id:
        log.info("analyze_json", "認証済みユーザー", user_id=validated.user_id)

    try:
        # Cache check（画像の存在も確認し、なければ再生成を促す）
        paper_id, raw_text = _resolve_cached_paper(
            validated.file_hash, storage, "analyze_json"
        )

        task_id = str(uuid.uuid4())

        # Save session context immediately if using existing paper AND registered
        if validated.is_registered and session_id and paper_id and paper_id != "pending":
            try:
                storage.save_session_context(session_id, paper_id)
                log.info(
                    "analyze_json",
                    "セッションコンテキストを事前保存しました",
                    session_id=session_id,
                    paper_id=paper_id,
                )
            except Exception as e:
                log.error(
                    "analyze_json", "Failed to pre-save session context", error=str(e)
                )

        task_data: dict = {
            "format": "json",
            "lang": validated.lang,
            "session_id": session_id,
            "filename": file.filename,
            "file_hash": validated.file_hash,
            "user_id": validated.user_id,
            "is_registered": validated.is_registered,
            "paper_id": paper_id,
        }

        if raw_text is None:
            # Save PDF to disk instead of Redis to prevent OOM
            doc_path = img_storage.save_doc(validated.file_hash, validated.content)
            log.info(
                "analyze_json",
                "PDFをストレージに保存しました",
                file_hash=validated.file_hash,
                doc_path=doc_path,
                content_size=len(validated.content),
                magic_hex=validated.content[:8].hex() if validated.content else "",
            )
            task_data.update({"pending_ocr": True, "pdf_path": doc_path})

            # Cloud Tasks が設定されている場合はワーカーにエンキュー（インライン処理回避）
            from app.providers.cloud_tasks import enqueue_ocr_task  # noqa: PLC0415

            worker_payload = {
                "pdf_path": doc_path,
                "file_hash": validated.file_hash,
                "filename": file.filename or "unknown.pdf",
                "lang": validated.lang,
                "user_id": validated.user_id,
                "is_registered": validated.is_registered,
                "session_id": session_id,
                "paper_id": paper_id,
            }
            enqueued = await enqueue_ocr_task(task_id, worker_payload)
            task_data["status"] = "queued" if enqueued else "inline"
        else:
            task_data.update({"text": raw_text})

        # Set 1-hour sliding expiration for paper sessions (3600s)
        redis_service.set(f"task:{task_id}", task_data, expire=3600)

        total_elapsed = time.time() - start_time
        log.info(
            "analyze_json",
            "タスクを作成しました",
            task_id=task_id,
            elapsed=f"{total_elapsed:.2f}s",
        )

        return JSONResponse(
            {"task_id": task_id, "stream_url": f"/api/stream/{task_id}"}
        )

    except Exception as e:
        log.error(
            "analyze_json", "予期せぬエラーが発生しました", error=str(e), exc_info=True
        )

        error_msg = (
            str(e)
            if not is_production()
            else "An error occurred while analyzing the document."
        )
        return JSONResponse({"error": error_msg}, status_code=500)


class AnalyzePdfHashRequest(BaseModel):
    """GCS 直接アップロード済み PDF の解析開始リクエスト。"""

    file_hash: str
    filename: str
    lang: str = "ja"
    session_id: str | None = None


@router.get("/pdf/request-upload-url")
async def request_upload_url(
    file_hash: str = Query(...),
    file_size_bytes: int = Query(...),
    _user: OptionalUser = None,
):
    """
    GCS への直接 PUT アップロード用の署名付き URL を返す。
    STORAGE_TYPE=local の場合は upload_url=None を返し、
    フロントエンドは従来の /api/analyze-pdf-json にフォールバックする。
    """
    # file_hash 形式検証（64文字の16進数）
    if not re.fullmatch(r"[0-9a-f]{64}", file_hash):
        return JSONResponse({"error": "Invalid file_hash format"}, status_code=422)

    # ファイルサイズ検証
    max_pdf_bytes = int(settings.get("MAX_PDF_SIZE_MB", "50")) * 1024 * 1024
    max_pdf_mb = max_pdf_bytes // (1024 * 1024)
    if file_size_bytes > max_pdf_bytes:
        return JSONResponse(
            {
                "error": f"File too large. Maximum size is {max_pdf_mb}MB.",
                "max_mb": max_pdf_mb,
            },
            status_code=413,
        )
    if file_size_bytes <= 0:
        return JSONResponse(
            {"error": "file_size_bytes must be positive"}, status_code=422
        )

    # キャッシュ確認
    storage = get_storage_provider()
    cached_paper = storage.get_paper_by_hash(file_hash)
    # Check if BOTH metadata and PDF source exist
    # If GCS blob is missing, we must NOT use already_cached=True,
    # because the next stage (/api/pdf/analyze-pdf-hash) checks for it.
    already_cached = (cached_paper is not None) and pdf_blob_exists(file_hash)

    # 署名付き URL 生成（LocalImageStorage なら None が返る）
    upload_url = get_upload_signed_url(file_hash)

    log.info(
        "request_upload_url",
        "アップロード URL リクエスト",
        file_hash=file_hash,
        already_cached=already_cached,
        has_upload_url=upload_url is not None,
    )

    return JSONResponse(
        {
            "upload_url": upload_url,
            "already_cached": already_cached,
        }
    )


@router.post("/pdf/analyze-pdf-hash")
async def analyze_pdf_hash(
    req: AnalyzePdfHashRequest,
    user: OptionalUser = None,
):
    """
    GCS に直接アップロード済みの PDF の解析を開始する。
    ファイル受取・ハッシュ計算・GCS 保存をスキップした analyze-pdf-json の変種。
    """
    import time

    start_time = time.time()

    # file_hash 形式検証
    if not re.fullmatch(r"[0-9a-f]{64}", req.file_hash):
        return JSONResponse({"error": "Invalid file_hash format"}, status_code=422)

    # GCS 上のファイル存在確認
    if not pdf_blob_exists(req.file_hash):
        return JSONResponse(
            {"error": "PDF not found in storage. Please re-upload."},
            status_code=404,
        )

    storage = get_storage_provider()
    user_id = (
        user.uid if user else (f"guest:{req.session_id}" if req.session_id else None)
    )
    is_registered = get_is_registered(user_id)

    # キャッシュ確認
    paper_id, raw_text = _resolve_cached_paper(
        req.file_hash, storage, "analyze_hash"
    )

    task_id = str(uuid.uuid4())

    # セッションコンテキストの事前保存
    if is_registered and req.session_id and paper_id and paper_id != "pending":
        try:
            storage.save_session_context(req.session_id, paper_id)
        except Exception as e:
            log.error(
                "analyze_hash", "Failed to pre-save session context", error=str(e)
            )

    task_data = {
        "format": "json",
        "lang": req.lang,
        "session_id": req.session_id,
        "filename": req.filename,
        "file_hash": req.file_hash,
        "user_id": user_id,
        "is_registered": is_registered,
        "paper_id": paper_id,
    }

    if raw_text is None:
        doc_path = img_storage.get_doc_path(req.file_hash)
        task_data.update({"pending_ocr": True, "pdf_path": doc_path})

        # Cloud Tasks が設定されている場合はワーカーにエンキュー
        from app.providers.cloud_tasks import enqueue_ocr_task  # noqa: PLC0415

        worker_payload = {
            "pdf_path": doc_path,
            "file_hash": req.file_hash,
            "filename": req.filename,
            "lang": req.lang,
            "user_id": user_id,
            "is_registered": is_registered,
            "session_id": req.session_id,
            "paper_id": paper_id,
        }
        enqueued = await enqueue_ocr_task(task_id, worker_payload)
        task_data["status"] = "queued" if enqueued else "inline"
    else:
        task_data.update({"text": raw_text})

    redis_service.set(f"task:{task_id}", task_data, expire=3600)

    elapsed = time.time() - start_time
    log.info(
        "analyze_hash",
        "タスクを作成しました",
        task_id=task_id,
        elapsed=f"{elapsed:.2f}s",
    )

    return JSONResponse({"task_id": task_id, "stream_url": f"/api/stream/{task_id}"})


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
        storage = get_storage_provider()
        paper = storage.get_paper(paper_id)
        if not paper:
            return JSONResponse({"error": "Paper not found"}, status_code=404)

        file_hash = paper.get("file_hash")
        if not file_hash:
            return JSONResponse(
                {"error": "Paper record is corrupt (missing hash)"}, status_code=400
            )

        user_id = user.uid if user else (f"guest:{session_id}" if session_id else None)
        is_registered = get_is_registered(user_id)

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
            "論文解析の開始中にエラーが発生しました",
            error=str(e),
            paper_id=paper_id,
        )
        error_msg = (
            str(e)
            if not is_production()
            else "An error occurred while analyzing the document."
        )
        return JSONResponse({"error": error_msg}, status_code=500)


async def _poll_worker_progress(task_id: str):
    """Cloud Tasks ワーカーが Redis リストに書き込む進捗イベントをポーリングして yield する。"""
    progress_key = f"task:progress:{task_id}"
    POLL_TIMEOUT = 300.0  # 5 分でタイムアウト
    start = time.time()

    while time.time() - start < POLL_TIMEOUT:
        item = redis_service.lpop(progress_key)
        if item:
            try:
                payload = json.loads(item) if isinstance(item, str) else item
            except Exception:
                payload = {"type": "error", "message": "invalid progress event"}

            yield f"event: message\ndata: {json.dumps(payload)}\n\n"

            ptype = payload.get("type")
            if ptype in ("done", "error"):
                return
        else:
            # ワーカーがまだ書き込んでいない場合はタスクステータスを確認
            fresh = redis_service.get(f"task:{task_id}")
            if not fresh:
                yield f"event: message\ndata: {json.dumps({'type': 'error', 'message': 'task expired'})}\n\n"
                return
            if fresh.get("status") == "error":
                yield f"event: message\ndata: {json.dumps({'type': 'error', 'message': 'worker failed'})}\n\n"
                return
            await asyncio.sleep(0.2)

    yield f"event: message\ndata: {json.dumps({'type': 'error', 'message': 'OCR worker timeout'})}\n\n"


@router.get("/stream/{task_id}")
async def stream(task_id: str):
    stream_start = time.time()
    last_heartbeat = time.time()
    HEARTBEAT_INTERVAL = 15.0

    log.info("stream", "開始", task_id=task_id)

    data = redis_service.get(f"task:{task_id}")
    if data:
        # Refresh task TTL on access
        redis_service.expire(f"task:{task_id}", 3600)

    # Task not found - return proper error response instead of 204
    if not data:
        log.warning("stream", "タスクが見つからないか、期限切れです", task_id=task_id)

        return Response(
            content=f"data: {json.dumps({'type': 'error', 'message': 'Task not found or expired'})}\n\n",
            media_type="text/event-stream",
            status_code=200,
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
        )

    is_json = data.get("format") == "json"
    text = data.get("text", "")
    paper_id = data.get("paper_id")
    lang = data.get("lang", "ja")
    session_id = data.get("session_id")
    user_id = data.get("user_id")  # Retrieve user_id
    is_registered = data.get("is_registered", False)
    file_hash = data.get("file_hash", "")
    filename = data.get("filename", "unknown.pdf")
    paper_title = data.get("paper_title")

    # 論文タイトルの事前取得 (HTMX リンク埋め込み用)
    if not paper_title and paper_id and paper_id != "pending":
        storage = get_storage_provider()
        paper_obj = storage.get_paper(paper_id)
        if paper_obj:
            paper_title = paper_obj.get("title") or paper_obj.get("filename")

    if not paper_title:
        paper_title = filename

    # --- JSON STREAMING HANDLER ---
    if is_json:

        async def _inner_json_generate():
            nonlocal last_heartbeat
            storage = get_storage_provider()
            try:
                if data.get("pending_ocr"):
                    # Cloud Tasks ワーカーが処理中 → Redis リストをポーリング
                    if data.get("status") in ("queued", "processing"):
                        async for event_str in _poll_worker_progress(task_id):
                            now = time.time()
                            if now - last_heartbeat > HEARTBEAT_INTERVAL:
                                yield ": heartbeat\n\n"
                                last_heartbeat = now
                            yield event_str
                        return

                    # ローカル / フォールバック: OCR インライン処理
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
                        log.error("stream", "PDFソースが見つかりません", task_id=task_id)

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
                        "OCR抽出を開始します",
                        task_id=task_id,
                        filename=filename,
                    )

                    # Collect figures to save later
                    collected_figures = []

                    page_count = 0
                    async for result_tuple in service.ocr_service.extract_text_streaming(
                        pdf_content, filename, user_plan=user_plan
                    ):
                        # Check for Heartbeat
                        now = time.time()
                        if now - last_heartbeat > HEARTBEAT_INTERVAL:
                            yield ": heartbeat\n\n"
                            last_heartbeat = now

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

                            if layout_data:
                                # Phase 3 確定結果のみ DB 保存用データに追加
                                full_text_fragments.append(page_text)
                                page_payload["width"] = layout_data["width"]
                                page_payload["height"] = layout_data["height"]
                                page_payload["words"] = layout_data.get("words", [])
                                page_payload["figures"] = layout_data.get("figures", [])

                                # Collect figures if present
                                if "figures" in layout_data:
                                    collected_figures.extend(layout_data["figures"])

                                all_layout_data.append(layout_data)
                            # layout_data=None は Phase 1/2 の速報値（DB保存対象外）

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

                    # 処理フラグ集計: ページごとの _ocr_engine からペーパー全体のエンジンを算出
                    _page_engines = {
                        ld.get("_ocr_engine", "native")
                        for ld in all_layout_data
                        if ld and isinstance(ld, dict)
                    }
                    _scanned_count = sum(
                        1
                        for ld in all_layout_data
                        if ld and isinstance(ld, dict) and ld.get("_ocr_engine") in ("ocrmypdf", "tesseract")
                    )
                    if len(_page_engines) == 1:
                        _ocr_engine = next(iter(_page_engines))
                    elif _page_engines:
                        _ocr_engine = "mixed"
                    else:
                        _ocr_engine = "native"

                    # Save to permanent DB ONLY for registered users (prevent DB clutter for transient guest sessions)
                    # Transient sessions rely on Redis and Frontend IndexedDB.
                    _db_saved = True  # DB 保存成功フラグ（フロントエンドの layout 解析トリガー制御用）
                    if is_registered:
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
                                ocr_engine=_ocr_engine,
                                scanned_page_count=_scanned_count,
                            )
                            # DBにもセッションマッピングを保存
                            if session_id:
                                storage.save_session_context(session_id, new_paper_id)

                            # layout_json はインライン処理で保存済みのため layout_status を更新
                            storage.update_processing_status(new_paper_id, "layout_status", "success")

                            log.info(
                                "stream",
                                f"ユーザー {user_id} の論文をDBに保存しました",
                                task_id=task_id,
                                user_id=user_id,
                                paper_id=new_paper_id,
                            )

                            # PDF メタデータ（fitz.metadata）から title / authors を即時保存
                            try:
                                import fitz as _fitz  # noqa: PLC0415

                                with _fitz.open(stream=pdf_content, filetype="pdf") as _doc:
                                    _meta = _doc.metadata
                                _pdf_title = (_meta.get("title") or "").strip() or None
                                _pdf_authors = (_meta.get("author") or "").strip() or None
                                if _pdf_title:
                                    storage.update_paper_title(new_paper_id, _pdf_title)
                                if _pdf_authors:
                                    storage.update_paper_authors(new_paper_id, _pdf_authors)
                            except Exception as _meta_err:
                                log.warning(
                                    "stream",
                                    "PDF メタデータ取得に失敗（無視）",
                                    error=str(_meta_err),
                                )

                            # Trigger background tasks (require DB records)
                            asyncio.create_task(
                                process_paper_summary_task(new_paper_id, lang=lang)
                            )

                            # GROBID 非同期エンリッチメントジョブをエンキュー
                            from app.domain.services.paper_processing import (  # noqa: PLC0415
                                process_grobid_enrichment_task,
                            )
                            asyncio.create_task(
                                process_grobid_enrichment_task(new_paper_id, file_hash)
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
                                f"DBへの保存に失敗しました: {db_err}",
                                task_id=task_id,
                                paper_id=new_paper_id,
                            )
                            _db_saved = False

                    else:
                        log.warning(
                            "stream",
                            "DBへの保存をスキップ: is_registered=False (ゲストまたは未登録ユーザー)",
                            task_id=task_id,
                            user_id=user_id,
                            is_guest=str(user_id).startswith("guest") if user_id else True,
                        )

                    # Redis session context (1-hour sliding limit, TRUNCATED to 20k chars to prevent OOM)
                    s_id = session_id or new_paper_id
                    # Store only the first 20,000 characters in Redis as "recent context"
                    recent_context = full_text[:20000]
                    redis_service.set(f"session:ctx:{s_id}", recent_context, expire=3600)

                    yield f"event: message\ndata: {json.dumps({'type': 'done', 'paper_id': new_paper_id, 'db_saved': _db_saved})}\n\n"
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
                                    "DBからレイアウト情報を読み込みました",
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
                            "キャッシュされた画像が見つかりました",
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
                                    f"ページ {i + 1} をキャッシュから読み込みました",
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
                            f"session:ctx:{s_id}", paper_data["ocr_text"], expire=3600
                        )  # Align TTL to 1 hour
                        log.info(
                            "stream",
                            "セッションコンテキストを復元しました",
                            s_id=s_id,
                        )

                    # DBのセッション→論文マッピングも更新（レビュー等が正しい論文を参照するため）
                    if is_registered and session_id and paper_id:
                        try:
                            storage.save_session_context(session_id, paper_id)
                        except Exception as e:
                            log.warning(
                                "stream",
                                "キャッシュ論文のセッションコンテキスト保存に失敗しました",
                                session_id=session_id,
                                paper_id=paper_id,
                                error=str(e),
                            )

                    else:
                        log.warning(
                            "stream",
                            "セッションコンテキストの復元に失敗しました",
                            session_id=session_id,
                            has_paper_data=paper_data is not None,
                        )

                    yield f"event: message\ndata: {json.dumps({'type': 'done', 'paper_id': paper_id, 'cached': True})}\n\n"
                    await asyncio.sleep(0.01)

            except Exception as e:
                log.error("stream_inner", f"Error in generator: {e}", task_id=task_id, exc_info=True)
                yield f"event: message\ndata: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"
            finally:
                if storage:
                    storage.close()
                    log.debug("stream_inner", "Closed DB storage session", task_id=task_id)

            log.info("stream", "JSON生成が完了しました", task_id=task_id)

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
            storage = get_storage_provider()
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
                        import html as _html

                        safe_title = _html.escape(paper_title) if paper_title else ""
                        words_html.append(
                            f'<a id="{word_id}" class="absolute cursor-pointer hover:bg-yellow-300/30 transition-colors rounded-sm group"'
                            f' style="left:{left}%; top:{top}%; width:{width}%; height:{height}%;"'
                            f' hx-get="/translate/{word_text}?lang={lang}&element_id={word_id}&paper_title={safe_title}"'
                            f' hx-vals=\'js:{{context: document.getElementById("{word_id}").closest(".text-line")?.innerText?.slice(0, 300) || ""}}\''
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
                        session_id=session_id,
                        paper_title=paper_title,
                    ):
                        yield chunk
                        await asyncio.sleep(0.005)

            # 全ページ完了後、DB保存 (Backup for analysis tasks)
            full_text = "\n\n---\n\n".join(full_text_fragments)

            if is_registered:
                try:
                    storage.save_paper(
                        paper_id=paper_id,
                        file_hash=file_hash,
                        filename=filename,
                        ocr_text=full_text,
                        html_content="",
                        target_language="ja",
                        layout_json=json.dumps(all_layout_data),
                        owner_id=user_id,
                    )
                    # layout_json はインライン処理で保存済みのため layout_status を更新
                    storage.update_processing_status(paper_id, "layout_status", "success")
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
                                process_figure_analysis_task(
                                    fid,
                                    fig["image_url"],
                                    user_id=user_id,
                                    session_id=session_id,
                                )
                            )

                    # --- Auto-Summarization for Abstract ---
                    asyncio.create_task(
                        process_paper_summary_task(
                            paper_id, lang=lang, user_id=user_id, session_id=session_id
                        )
                    )

                    # DBにもセッションマッピングを保存
                    if session_id:
                        storage.save_session_context(session_id, paper_id)

                except Exception as e:
                    log.error(
                        "ocr_generate",
                        f"Failed to save paper record: {e}",
                        paper_id=paper_id,
                    )
            else:
                log.warning(
                    "ocr_generate",
                    "DBへの保存をスキップ: is_registered=False (ゲストまたは未登録ユーザー)",
                    paper_id=paper_id,
                    user_id=user_id,
                    is_guest=str(user_id).startswith("guest") if user_id else True,
                )

            # Redisセッションコンテキストを1時間保持 (sliding)
            if session_id:
                redis_service.set(f"session:ctx:{session_id}", full_text, expire=3600)

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
        async for chunk in service.tokenize_stream(
            text, paper_id, lang=lang, session_id=session_id
        ):
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
