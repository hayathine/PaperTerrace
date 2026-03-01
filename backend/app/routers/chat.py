"""
Chat Router
Handles chat interactions with the AI assistant.
"""

import json

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
from common.logger import get_service_logger

log = get_service_logger("Chat")

router = APIRouter(tags=["Chat"])

# Services
chat_service = ChatService()
redis_service = RedisService()
storage = get_storage_provider()


class ChatRequest(BaseModel):
    message: str
    session_id: str
    lang: str = "ja"
    paper_id: str | None = None
    figure_id: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest, user: OptionalUser = None):
    # Check registration status
    user_id = user.uid if user else None
    is_registered = False
    if user_id:
        if storage.get_user(user_id):
            is_registered = True

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
        expire = 30 * 24 * 3600  # 30 days for registered users
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
                log.debug(
                    "chat", "PDF bytes loaded for grounding", paper_id=paper_id
                )
        except Exception as e:
            log.warning("chat", f"Failed to load PDF bytes for grounding: {e}")

    response_data = await chat_service.chat(
        request.message,
        history=history,
        document_context=context,
        target_lang=request.lang,
        paper_id=paper_id,
        image_bytes=image_bytes,
        pdf_bytes=pdf_bytes,
    )

    # Handle grounding if available
    if isinstance(response_data, dict):
        response_text = response_data["text"]
        grounding = response_data.get("grounding")
    else:
        response_text = response_data
        grounding = None

    # Update history
    history.append({"role": "user", "content": request.message})
    history.append(
        {"role": "assistant", "content": response_text, "grounding": grounding}
    )

    # Trim history (keep last 40)
    if len(history) > 40:
        history = history[-40:]

    # Save to cache & Refresh context TTL
    redis_service.set(history_key, json.dumps(history), expire=expire)
    if context:
        redis_service.expire(f"session:{request.session_id}", 3600)

    return JSONResponse(
        {
            "response": response_text,
            "grounding": grounding,
        }
    )


@router.get("/chat/history")
async def get_chat_history(
    session_id: str, paper_id: str | None = None, user: OptionalUser = None
):
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

    return JSONResponse({"history": history})


@router.post("/chat/clear")
async def clear_chat(
    session_id: str = Form(...),
    paper_id: str | None = Form(None),
    user: OptionalUser = None,
):
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
        paper_id = storage.get_session_paper_id(session_id)

    if paper_id:
        # Prevent cache deletion to avoid re-uploading context on page refresh
        # await chat_service.delete_paper_cache(paper_id)
        return JSONResponse({"status": "ok"})

    return JSONResponse(
        {"status": "error", "message": "No paper_id provided"}, status_code=400
    )
