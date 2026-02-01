"""
Chat Router
Handles chat interactions with the AI assistant.
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from src.domain.features import ChatService
from src.core.logger import logger
from src.infra import RedisService

router = APIRouter(tags=["Chat"])

# Services
chat_service = ChatService()
redis_service = RedisService()


class ChatRequest(BaseModel):
    message: str
    session_id: str
    author_mode: bool = False
    lang: str = "ja"


@router.post("/chat")
async def chat(request: ChatRequest):
    logger.info(
        f"[Chat] Request for session {request.request_id if hasattr(request, 'request_id') else request.session_id}"
    )
    try:
        context = redis_service.get(f"session:{request.session_id}") or ""

        if request.author_mode:
            response = await chat_service.author_agent_response(
                request.message, context, target_lang=request.lang
            )
        else:
            response = await chat_service.chat(request.message, context, target_lang=request.lang)

        return JSONResponse({"response": response})
    except Exception as e:
        logger.exception(f"[Chat] Error in chat session {request.session_id}")
        return JSONResponse({"error": str(e)}, status_code=500)


@router.post("/chat/clear")
async def clear_chat(session_id: str = Form(...)):
    try:
        logger.info(f"[Chat] Clearing history for session {session_id}")
        chat_service.clear_history()
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.exception(f"[Chat] Failed to clear history for session {session_id}")
        return JSONResponse({"error": str(e)}, status_code=500)
