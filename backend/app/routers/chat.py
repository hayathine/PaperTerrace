"""
Chat Router
Handles chat interactions with the AI assistant.
"""

import json
import re
from typing import Literal

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from common import settings

from app.auth import OptionalUser
from app.domain.features import ChatService
from app.domain.features.cache_utils import get_pdf_cache_key
from app.providers import (
    RedisService,
    get_image_bytes,
    get_storage_provider,
)  # RedisService now uses in-memory cache
from common.logger import ServiceLogger
from redis_provider.provider import get_is_registered

log = ServiceLogger("Chat")


router = APIRouter(tags=["Chat"])

# Services
chat_service = ChatService()
redis_service = RedisService()


_SESSION_ID_RE = re.compile(r"^[a-zA-Z0-9_\-]{1,128}$")


class ChatRequest(BaseModel):
    message: str
    session_id: str
    lang: str = "ja"
    paper_id: str | None = None
    figure_id: str | None = None

    @field_validator("session_id")
    @classmethod
    def validate_session_id(cls, v: str) -> str:
        """セッションIDが英数字・ハイフン・アンダースコアのみで構成されているか検証する。"""
        if not _SESSION_ID_RE.match(v):
            raise ValueError("session_id contains invalid characters")
        return v

    @field_validator("lang")
    @classmethod
    def normalize_lang(cls, v: str) -> Literal["ja", "en"]:
        """'ja-JP' などのロケール文字列を 'ja'/'en' に正規化する。"""
        if v.startswith("ja"):
            return "ja"
        return "en"

    @field_validator("message")
    @classmethod
    def sanitize_message(cls, v: str) -> str:
        """NULバイト除去と長さ制限を適用する。"""
        v = v.replace("\0", "")
        max_len = int(settings.get("MAX_CHAT_MESSAGE_LENGTH", "4000"))
        return v[:max_len]


@router.post("/chat")
async def chat(request: ChatRequest, user: OptionalUser = None):
    import time

    t_start = time.perf_counter()
    storage = get_storage_provider()

    # 1. Auth & Redis cache check
    user_id = user.uid if user else None
    is_registered = get_is_registered(user_id)
    t_auth = time.perf_counter()

    sanitized_message = request.message

    # 2. Resolve paper_id
    paper_id = request.paper_id
    if not paper_id:
        paper_id = storage.get_session_paper_id(request.session_id)
    t_paper_resolve = time.perf_counter()

    # 3. History key
    if is_registered:
        history_key = (
            f"chat:user:{user_id}:{request.paper_id if request.paper_id else 'global'}"
        )
        expire = 7 * 24 * 3600
    else:
        history_key = f"chat:guest:{request.session_id}:{request.paper_id if request.paper_id else 'global'}"
        expire = 3600

    # 4. Context & History from Redis
    session_key = f"session:ctx:{request.session_id}"
    context_raw, history_raw = redis_service.mget(session_key, history_key)
    context = context_raw or ""
    history = history_raw or []
    t_redis_load = time.perf_counter()

    # Sliding window/Context refresh
    if context:
        redis_service.expire(session_key, 3600)

    # 5. Chat turn limit
    user_msg_count = sum(1 for m in history if m.get("role") == "user")
    max_turns = int(settings.get("MAX_CHAT_TURNS", "50"))
    if user_msg_count >= max_turns:
        return JSONResponse(
            {
                "response": f"チャットの最大回数（{max_turns}回）に達しました。新しいセッションを開始するか、履歴をクリアしてください。"
            }
        )

    # 6. Image Load (if figure_id)
    image_bytes = None
    if request.figure_id:
        figure = storage.get_figure(request.figure_id)
        if figure and figure.get("image_url"):
            try:
                image_bytes = get_image_bytes(figure["image_url"])
                log.debug("chat", "画像を読み込みました", figure_id=request.figure_id)
            except Exception as e:
                log.warning("chat", "画像の読み込みに失敗しました", figure_id=request.figure_id, error=str(e))
    t_image_load = time.perf_counter()

    # 7. PDF Grounding Download (THE BIG POTENTIAL NECK)
    MAX_CHAT_PDF_BYTES = int(settings.get("MAX_CHAT_PDF_SIZE_MB", "30")) * 1024 * 1024
    pdf_input: bytes | str | None = None
    t_pdf_download_start = time.perf_counter()
    if paper_id:
        pdf_cache_key = get_pdf_cache_key(paper_id)
        # If cache exists in Redis, we skip download as ChatService will use the cache
        if redis_service.get(pdf_cache_key):
            log.debug("chat", "PDFキャッシュ存在のためダウンロードスキップ", paper_id=paper_id)
        else:
            try:
                paper_info = storage.get_paper(paper_id)
                if paper_info and paper_info.get("file_hash"):
                    from app.providers.image_storage import get_image_storage, GCSImageStorage
                    img_storage = get_image_storage()
                    
                    if isinstance(img_storage, GCSImageStorage):
                        doc_path = img_storage.get_doc_path(paper_info["file_hash"])
                        pdf_input = f"gs://{img_storage.bucket_name}/{doc_path}"
                        log.debug("chat", "GCS URIをチャット用に解決", uri=pdf_input)
                    else:
                        pdf_input = img_storage.get_doc_bytes(
                            img_storage.get_doc_path(paper_info["file_hash"])
                        )
                        if pdf_input and len(pdf_input) > MAX_CHAT_PDF_BYTES:
                            log.warning("chat", "PDFサイズ超過のためGroundingスキップ")
                            pdf_input = None
            except Exception as e:
                log.warning("chat", "Grounding用PDFの取得に失敗(non-fatal)", error=str(e))
    t_pdf_download_end = time.perf_counter()

    # 8. AI Generation (The core processing)
    current_user_id = user_id if is_registered else f"guest:{request.session_id}"
    ai_start = time.perf_counter()
    response_data = await chat_service.chat(
        sanitized_message,
        history=history,
        document_context=context,
        target_lang=request.lang,
        paper_id=paper_id,
        user_id=current_user_id,
        session_id=request.session_id,
        image_bytes=image_bytes,
        pdf_input=pdf_input,
    )
    ai_end = time.perf_counter()

    # Unpack response
    # response_data is expected to be a dict {"text": ..., "trace_id": ..., "grounding": ...}
    if isinstance(response_data, str):
        response_text = response_data
        grounding = None
        trace_id = None
    else:
        response_text = response_data["text"]
        grounding = response_data.get("grounding")
        trace_id = response_data.get("trace_id")

    # Final Timings Log
    total_s = ai_end - t_start
    log.info(
        "chat_timing",
        "Chat request processed",
        total_s=round(total_s, 3),
        auth_s=round(t_auth - t_start, 3),
        redis_s=round(t_redis_load - t_paper_resolve, 3),
        image_s=round(t_image_load - t_redis_load, 3),
        pdf_download_s=round(t_pdf_download_end - t_pdf_download_start, 3),
        ai_call_s=round(ai_end - ai_start, 3),
        paper_id=paper_id,
    )

    # 9. Update History
    history.append({"role": "user", "content": sanitized_message})
    history.append(
        {
            "role": "assistant",
            "content": response_text,
            "grounding": grounding,
            "trace_id": trace_id,
        }
    )

    # Trim history
    max_history = int(settings.get("MAX_CHAT_HISTORY_MESSAGES", "200"))
    if len(history) > max_history:
        history = history[-max_history:]

    # Save update
    redis_service.set(history_key, json.dumps(history), expire=expire)
    if context:
        redis_service.expire(f"session:ctx:{request.session_id}", 3600)

    # Permament storage
    if is_registered and paper_id:
        try:
            storage.save_chat_history(user_id, paper_id, history)
        except Exception as e:
            log.warning("chat", "History persistence failed", error=str(e))

    return JSONResponse(
        {
            "response": response_text,
            "grounding": grounding,
            "trace_id": trace_id,
        }
    )



@router.get("/chat/history")
async def get_chat_history(
    session_id: str, paper_id: str | None = None, user: OptionalUser = None
):
    storage = get_storage_provider()
    user_id = user.uid if user else None
    is_registered = get_is_registered(user_id)

    if is_registered:
        history_key = f"chat:user:{user_id}:{paper_id if paper_id else 'global'}"
    else:
        history_key = f"chat:guest:{session_id}:{paper_id if paper_id else 'global'}"

    history = redis_service.get(history_key) or []

    # Redis にない場合、登録ユーザーは PostgreSQL からフォールバック
    if not history and is_registered and paper_id:
        try:
            history = storage.get_chat_history(user_id, paper_id)
            if history:
                # Redis に復元（7日TTL）
                redis_service.set(
                    history_key, json.dumps(history), expire=7 * 24 * 3600
                )
        except Exception as e:
            log.warning(
                "chat_history", "DBからのチャット履歴の取得に失敗しました", error=str(e)
            )

    return JSONResponse({"history": history})


@router.post("/chat/clear")
async def clear_chat(
    session_id: str = Form(...),
    paper_id: str | None = Form(None),
    user: OptionalUser = None,
):
    user_id = user.uid if user else None
    is_registered = get_is_registered(user_id)

    if is_registered:
        history_key = f"chat:user:{user_id}:{paper_id if paper_id else 'global'}"
    else:
        history_key = f"chat:guest:{session_id}:{paper_id if paper_id else 'global'}"

    redis_service.delete(history_key)
    return JSONResponse({"status": "ok"})


@router.post("/chat/cache/delete")
async def delete_cache(session_id: str = Form(...), paper_id: str | None = Form(None)):
    """Delete the AI context cache for the given paper."""
    if not paper_id:
        storage = get_storage_provider()
        paper_id = storage.get_session_paper_id(session_id)

    if paper_id:
        # Prevent cache deletion to avoid re-uploading context on page refresh
        # await chat_service.delete_paper_cache(paper_id)
        return JSONResponse({"status": "ok"})

    return JSONResponse(
        {"status": "error", "message": "No paper_id provided"}, status_code=400
    )
