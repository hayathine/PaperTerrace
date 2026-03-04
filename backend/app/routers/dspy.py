from fastapi import APIRouter, HTTPException
from google.cloud import bigquery as bq

from app.providers.bigquery_log import BigQueryLogClient
from app.schemas.dspy import TraceCommentUpdate
from common.logger import ServiceLogger

log = ServiceLogger("DspyRouter")

router = APIRouter(prefix="/dspy", tags=["DSPy"])


@router.post("/trace/{trace_id}/copy")
async def mark_trace_copied(trace_id: str):
    """
    Mark a DSPy trace as copied by the user.
    This serves as a strong positive signal for optimization.
    """
    client = BigQueryLogClient.get_instance()
    table = client.table_ref("dspy_traces")

    sql = f"""
        UPDATE `{table}`
        SET is_copied = TRUE
        WHERE trace_id = @trace_id
    """
    params = [bq.ScalarQueryParameter("trace_id", "STRING", trace_id)]

    try:
        affected = client.execute_dml(sql, params)
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
    Add or update a comment for a DSPy trace.
    """
    client = BigQueryLogClient.get_instance()
    table = client.table_ref("dspy_traces")

    sql = f"""
        UPDATE `{table}`
        SET comment = @comment
        WHERE trace_id = @trace_id
    """
    params = [
        bq.ScalarQueryParameter("trace_id", "STRING", trace_id),
        bq.ScalarQueryParameter("comment", "STRING", body.comment),
    ]

    try:
        affected = client.execute_dml(sql, params)
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
