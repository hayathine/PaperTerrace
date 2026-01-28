"""
Chat Router
Handles chat interactions with the AI assistant.
"""

from fastapi import APIRouter, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..features import ChatService
from ..providers import RedisService

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
    context = redis_service.get(f"session:{request.session_id}") or ""

    if request.author_mode:
        response = await chat_service.author_agent_response(
            request.message, context, target_lang=request.lang
        )
    else:
        response = await chat_service.chat(request.message, context, target_lang=request.lang)

    return JSONResponse({"response": response})


@router.post("/chat/clear")
async def clear_chat(session_id: str = Form(...)):
    chat_service.clear_history()
    return JSONResponse({"status": "ok"})
