"""
クライアントエラーログエンドポイント。
フロントエンドからのエラーを受け取り BigQuery に蓄積する。
"""

import json

from fastapi import APIRouter, Request

from app.models.bigquery.schemas import ClientErrorData
from app.models.repositories.client_error_repository import ClientErrorRepository
from app.schemas.client_error import ClientErrorRequest
from common.logger import ServiceLogger

log = ServiceLogger("ClientErrors")

router = APIRouter(prefix="/client-errors", tags=["ClientErrors"])


def get_current_user_id(request: Request) -> str | None:
    return getattr(request.state, "user_id", None)


@router.post("", summary="フロントエンドエラーを記録する", status_code=204)
async def report_client_error(
    req: ClientErrorRequest,
    request: Request,
) -> None:
    """
    フロントエンドで発生したエラーを受け取り BigQuery に保存する。
    ユーザーには生のエラー情報を返さない。
    """
    user_id = get_current_user_id(request)
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

    log.warn(
        "report",
        "Client error received",
        component=req.component,
        operation=req.operation,
        message=req.message[:200],
    )

    repo = ClientErrorRepository()
    repo.create(error)
