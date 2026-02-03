"""
Chat Router
Handles chat interactions with the AI assistant.
"""

import json

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.domain.features import ChatService
from src.logger import get_service_logger
from src.providers import RedisService, get_image_bytes, get_storage_provider

log = get_service_logger("Chat")

router = APIRouter(tags=["Chat"])

# Services
chat_service = ChatService()
redis_service = RedisService()
storage = get_storage_provider()


class ChatRequest(BaseModel):
    message: str
    session_id: str
    author_mode: bool = False
    lang: str = "ja"
    paper_id: str | None = None
    figure_id: str | None = None


@router.post("/chat")
async def chat(request: ChatRequest):
    context = redis_service.get(f"session:{request.session_id}") or ""

    # Resolve paper_id
    paper_id = request.paper_id
    if not paper_id:
        paper_id = storage.get_session_paper_id(request.session_id)

    # Get history from Redis
    history_key = f"chat:{request.session_id}:{paper_id if paper_id else 'global'}"
    history = redis_service.get(history_key) or []

    if request.author_mode:
        response = await chat_service.author_agent_response(
            request.message, context, target_lang=request.lang
        )
        # Author agent is stateless/different flow? Or should we append to history too?
        # Usually author agent answers just the question. Let's not mix it with main chat history for now,
        # or treat it as a special interaction.
        # For now, let's keep it separate or just return without history update.
    else:
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
                        "chat", "Failed to load image", figure_id=request.figure_id, error=str(e)
                    )

        response = await chat_service.chat(
            request.message,
            history=history,
            document_context=context,
            target_lang=request.lang,
            paper_id=paper_id,
            image_bytes=image_bytes,
        )

        # Update history
        history.append({"role": "user", "content": request.message})
        history.append({"role": "assistant", "content": response})

        # Trim history (keep last 40)
        if len(history) > 40:
            history = history[-40:]

        # Save to Redis (TTL 24h = 86400s)
        redis_service.set(history_key, json.dumps(history), expire=86400)

    return JSONResponse({"response": response})


@router.get("/chat/history")
async def get_chat_history(session_id: str, paper_id: str | None = None):
    # Resolve paper_id if missing
    if not paper_id:
        paper_id = storage.get_session_paper_id(session_id)

    auth_key = f"chat:{session_id}:{paper_id if paper_id else 'global'}"
    history = redis_service.get(auth_key) or []

    return JSONResponse({"history": history})


@router.post("/chat/clear")
async def clear_chat(session_id: str = Form(...), paper_id: str | None = Form(None)):
    if not paper_id:
        paper_id = storage.get_session_paper_id(session_id)

    history_key = f"chat:{session_id}:{paper_id if paper_id else 'global'}"
    redis_service.delete(history_key)
    return JSONResponse({"status": "ok"})


@router.post("/chat/cache/delete")
async def delete_cache(session_id: str = Form(...), paper_id: str | None = Form(None)):
    """Delete the AI context cache for the given paper."""
    if not paper_id:
        paper_id = storage.get_session_paper_id(session_id)

    if paper_id:
        await chat_service.delete_paper_cache(paper_id)
        return JSONResponse({"status": "ok"})

    return JSONResponse({"status": "error", "message": "No paper_id provided"}, status_code=400)
