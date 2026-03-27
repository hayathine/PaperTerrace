from fastapi import APIRouter, HTTPException

from app.providers.pg_log import PgLogClient
from app.schemas.dspy import TraceCommentUpdate
from common.logger import ServiceLogger

log = ServiceLogger("DspyRouter")

router = APIRouter(prefix="/dspy", tags=["DSPy"])


@router.post("/trace/{trace_id}/copy")
async def mark_trace_copied(trace_id: str):
    """
    DSPy トレースをユーザーがコピーしたとしてマークする。
    最適化の強い正シグナルとなる。
    """
    client = PgLogClient.get_instance()
    sql = f"UPDATE {client.table_ref('dspy_traces')} SET is_copied = TRUE WHERE trace_id = :trace_id"

    try:
        affected = client.execute_dml(sql, {"trace_id": trace_id})
        if affected == 0:
            log.warning("mark_copied", "Trace not found", trace_id=trace_id)
            raise HTTPException(status_code=404, detail="Trace not found")
        log.info("mark_copied", "Trace marked as copied", trace_id=trace_id)
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "mark_copied", "Failed to update trace", error=str(e), trace_id=trace_id
        )
        raise HTTPException(status_code=500, detail="Failed to update trace")

    return {"status": "ok", "message": "Trace marked as copied"}


@router.post("/trace/{trace_id}/comment")
async def update_trace_comment(trace_id: str, body: TraceCommentUpdate):
    """
    DSPy トレースにコメントを追加・更新する。
    """
    client = PgLogClient.get_instance()
    sql = f"UPDATE {client.table_ref('dspy_traces')} SET comment = :comment WHERE trace_id = :trace_id"

    try:
        affected = client.execute_dml(sql, {"trace_id": trace_id, "comment": body.comment})
        if affected == 0:
            log.warning("update_comment", "Trace not found", trace_id=trace_id)
            raise HTTPException(status_code=404, detail="Trace not found")
        log.info("update_comment", "Trace comment updated", trace_id=trace_id)
    except HTTPException:
        raise
    except Exception as e:
        log.error(
            "update_comment", "Failed to update trace", error=str(e), trace_id=trace_id
        )
        raise HTTPException(status_code=500, detail="Failed to update trace")

    return {"status": "ok", "message": "Trace comment updated"}
