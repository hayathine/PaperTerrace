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
    storage = get_storage_provider()
    # Check registration status (Redis キャッシュ付き、DB フォールバック)
    user_id = user.uid if user else None
    is_registered = get_is_registered(user_id)

    sanitized_message = request.message  # @field_validator でサニタイズ済み

    # Resolve paper_id
    paper_id = request.paper_id
    if not paper_id:
        paper_id = storage.get_session_paper_id(request.session_id)

    # Get history key
    if is_registered:
        history_key = (
            f"chat:{user_id}:{request.paper_id if request.paper_id else 'global'}"
        )
        expire = 7 * 24 * 3600  # 7 days for registered users
    else:
        history_key = f"chat:{request.session_id}:{request.paper_id if request.paper_id else 'global'}"
        expire = 3600  # 1 hour for guests (sliding window)

    # セッションコンテキストと履歴を1往復で取得（Redis MGET）
    session_key = f"session:{request.session_id}"
    context_raw, history_raw = redis_service.mget(session_key, history_key)
    context = context_raw or ""
    history = history_raw or []
    if context:
        redis_service.expire(session_key, 3600)

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
                log.debug("chat", "画像を読み込みました", figure_id=request.figure_id)
            except Exception as e:
                log.error(
                    "chat",
                    "画像の読み込みに失敗しました",
                    figure_id=request.figure_id,
                    error=str(e),
                )

    # Fetch PDF bytes for grounding if paper_id exists
    # キャッシュが既にある場合はGCSダウンロードをスキップ
    MAX_CHAT_PDF_BYTES = int(settings.get("MAX_CHAT_PDF_SIZE_MB", "30")) * 1024 * 1024
    pdf_bytes = None
    if paper_id:
        pdf_cache_key = f"paper_cache_pdf:{paper_id}"
        if redis_service.get(pdf_cache_key):
            log.debug(
                "chat", "PDFキャッシュが存在するため、GCSからのダウンロードをスキップします", paper_id=paper_id
            )
        else:
            try:
                paper_info = storage.get_paper(paper_id)
                if paper_info and paper_info.get("file_hash"):
                    from app.providers import get_image_storage

                    img_storage = get_image_storage()
                    pdf_bytes = img_storage.get_doc_bytes(
                        img_storage.get_doc_path(paper_info["file_hash"])
                    )
                    if len(pdf_bytes) > MAX_CHAT_PDF_BYTES:
                        log.warning(
                            "chat",
                            "PDFサイズが上限を超えたため、テキストコンテキストのみで処理します",
                            paper_id=paper_id,
                            pdf_size_mb=f"{len(pdf_bytes) / 1024 / 1024:.1f}",
                            limit_mb=settings.get("MAX_CHAT_PDF_SIZE_MB", "30"),
                        )
                        pdf_bytes = None
                    else:
                        log.debug(
                            "chat", "GroundingのためにPDFバイナリを読み込みました", paper_id=paper_id
                        )
            except Exception as e:
                log.warning(
                    "chat",
                    "Grounding用のPDFバイナリの読み込みに失敗しました",
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
            log.warning("chat", "DBへのチャット履歴の永続化に失敗しました", error=str(e))

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
