"""
クライアントエラーログエンドポイント。
フロントエンドからのエラーを受け取り logs PostgreSQL に蓄積する。
"""

import json

from fastapi import APIRouter, Request

from app.models.log_schemas.schemas import ClientErrorData
from app.models.repositories.client_error_repository import ClientErrorRepository
from app.schemas.client_error import ClientErrorRequest
from common.logger import ServiceLogger

log = ServiceLogger("ClientErrors")

router = APIRouter(prefix="/client-errors", tags=["ClientErrors"])


@router.post("", summary="フロントエンドエラーを記録する", status_code=204)
async def report_client_error(
    req: ClientErrorRequest,
    request: Request,
) -> None:
    """
    フロントエンドで発生したエラーを受け取り logs PostgreSQL に保存する。
    ユーザーには生のエラー情報を返さない。
    """
    user_id = getattr(request.state, "user_id", None) or (
        f"guest:{req.session_id}" if req.session_id else None
    )
    user_agent = request.headers.get("user-agent", "")[:500]

    context_str = json.dumps(req.context, ensure_ascii=False) if req.context else None

    error = ClientErrorData(
        message=req.message,
        component=req.component,
        operation=req.operation,
        user_id=user_id,
        error_name=req.error_name,
        stack=req.stack,
        context=context_str,
        url=req.url,
        user_agent=user_agent,
    )

    log.warning(
        "report",
        "Client error received",
        client_component=req.component,
        client_operation=req.operation,
        client_message=req.message[:200],
    )

    try:
        repo = ClientErrorRepository()
        repo.create(error)
    except Exception as e:
        log.error("report", f"Failed to initialize or write client error: {e}")

    try:
        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_tag("source", "frontend")
            scope.set_tag("component", req.component)
            scope.set_tag("operation", req.operation)
            if user_id:
                scope.set_user({"id": user_id})
            scope.set_extra("url", req.url)
            scope.set_extra("context", req.context)
            if req.stack:
                scope.set_extra("stack", req.stack)
            sentry_sdk.capture_message(
                f"[{req.component}.{req.operation}] {req.message}",
                level="error",
                scope=scope,
            )
    except Exception:
        pass
