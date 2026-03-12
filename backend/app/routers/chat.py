"""
Chat Router
Handles chat interactions with the AI assistant.
"""

import json
import os

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.auth import OptionalUser
from app.domain.features import ChatService
from app.providers import (
    RedisService,
    get_image_bytes,
    get_storage_provider,
)  # RedisService now uses in-memory cache
from common.logger import ServiceLogger

log = ServiceLogger("Chat")


router = APIRouter(tags=["Chat"])

# Services
chat_service = ChatService()
redis_service = RedisService()


_MAX_MESSAGE_LENGTH = int(os.getenv("MAX_CHAT_MESSAGE_LENGTH", "4000"))


def _sanitize_message(message: str) -> str:
    """ユーザーメッセージの基本的なサニタイズを行う。NULバイト除去と長さ制限を適用する。"""
    message = message.replace("\0", "")
    if len(message) > _MAX_MESSAGE_LENGTH:
        message = message[:_MAX_MESSAGE_LENGTH]
    return message


class ChatRequest(BaseModel):
    message: str
    session_id: str
    lang: str = "ja"
    paper_id: str | None = None
    figure_id: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest, user: OptionalUser = None):
    storage = get_storage_provider()
    # Check registration status
    user_id = user.uid if user else None
    is_registered = False
    if user_id:
        if storage.get_user(user_id):
            is_registered = True

    # ユーザーメッセージをサニタイズ
    sanitized_message = _sanitize_message(request.message)

    context = redis_service.get(f"session:{request.session_id}") or ""

    # Resolve paper_id
    paper_id = request.paper_id
    if not paper_id:
        paper_id = storage.get_session_paper_id(request.session_id)

    # Get history from Redis
    # Registered users: History linked to user_id and paper_id
    # Guests: History linked to session_id and paper_id
    if is_registered:
        history_key = (
            f"chat:{user_id}:{request.paper_id if request.paper_id else 'global'}"
        )
        expire = 7 * 24 * 3600  # 7 days for registered users
    else:
        history_key = f"chat:{request.session_id}:{request.paper_id if request.paper_id else 'global'}"
        expire = 3600  # 1 hour for guests (sliding window)

    history = redis_service.get(history_key) or []

    # Check chat limit (max 10 turns)
    user_msg_count = sum(1 for m in history if m.get("role") == "user")
    if user_msg_count >= 10:
        return JSONResponse(
            {
                "response": "チャットの最大回数（10回）に達しました。新しいセッションを開始するか、履歴をクリアしてください。"
            }
        )

    # Fetch image if figure_id provided
    image_bytes = None
    if request.figure_id:
        figure = storage.get_figure(request.figure_id)
        if figure and figure.get("image_url"):
            try:
                image_bytes = get_image_bytes(figure["image_url"])
                log.debug("chat", "Image loaded", figure_id=request.figure_id)
            except Exception as e:
                log.error(
                    "chat",
                    "Failed to load image",
                    figure_id=request.figure_id,
                    error=str(e),
                )

    # Fetch PDF bytes for grounding if paper_id exists
    pdf_bytes = None
    if paper_id:
        try:
            paper_info = storage.get_paper(paper_id)
            if paper_info and paper_info.get("file_hash"):
                from app.providers import get_image_storage

                img_storage = get_image_storage()
                pdf_bytes = img_storage.get_doc_bytes(
                    img_storage.get_doc_path(paper_info["file_hash"])
                )
                log.debug("chat", "PDF bytes loaded for grounding", paper_id=paper_id)
        except Exception as e:
            log.warning(
                "chat",
                "Failed to load PDF bytes for grounding",
                error=str(e),
                paper_id=paper_id,
            )

    # Calculate user_id (handling guest case)
    current_user_id = user_id if is_registered else f"guest:{request.session_id}"

    response_data = await chat_service.chat(
        sanitized_message,
        history=history,
        document_context=context,
        target_lang=request.lang,
        paper_id=paper_id,
        user_id=current_user_id,
        session_id=request.session_id,
        image_bytes=image_bytes,
        pdf_bytes=pdf_bytes,
    )

    # response_data is now ALWAYS a dict (containing 'text', 'trace_id', and optionally 'grounding')
    response_text = response_data["text"]
    grounding = response_data.get("grounding")
    trace_id = response_data.get("trace_id")

    # Update history
    history.append({"role": "user", "content": sanitized_message})
    history.append(
        {
            "role": "assistant",
            "content": response_text,
            "grounding": grounding,
            "trace_id": trace_id,
        }
    )

    # Trim history (keep last 40)
    if len(history) > 40:
        history = history[-40:]

    # Save to cache & Refresh context TTL
    redis_service.set(history_key, json.dumps(history), expire=expire)
    if context:
        redis_service.expire(f"session:{request.session_id}", 3600)

    # PostgreSQL に永続保存（登録ユーザー + paper_id がある場合のみ）
    if is_registered and paper_id:
        try:
            storage.save_chat_history(user_id, paper_id, history)
        except Exception as e:
            log.warning("chat", "Failed to persist chat history to DB", error=str(e))

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
    is_registered = False
    if user_id:
        if storage.get_user(user_id):
            is_registered = True

    if is_registered:
        history_key = f"chat:{user_id}:{paper_id if paper_id else 'global'}"
    else:
        history_key = f"chat:{session_id}:{paper_id if paper_id else 'global'}"

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
                "chat_history", "Failed to fetch chat history from DB", error=str(e)
            )

    return JSONResponse({"history": history})


@router.post("/chat/clear")
async def clear_chat(
    session_id: str = Form(...),
    paper_id: str | None = Form(None),
    user: OptionalUser = None,
):
    storage = get_storage_provider()
    user_id = user.uid if user else None
    is_registered = False
    if user_id:
        if storage.get_user(user_id):
            is_registered = True

    if is_registered:
        history_key = f"chat:{user_id}:{paper_id if paper_id else 'global'}"
    else:
        history_key = f"chat:{session_id}:{paper_id if paper_id else 'global'}"

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
