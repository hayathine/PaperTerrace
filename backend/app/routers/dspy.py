from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm.dspy_trace import DspyTrace
from app.schemas.dspy import TraceCommentUpdate
from common.logger import ServiceLogger

log = ServiceLogger("DspyRouter")

router = APIRouter(prefix="/dspy", tags=["DSPy"])


@router.post("/trace/{trace_id}/copy")
async def mark_trace_copied(trace_id: str, db: Session = Depends(get_db)):
    """
    Mark a DSPy trace as copied by the user.
    This serves as a strong positive signal for optimization.
    """
    trace = db.query(DspyTrace).filter(DspyTrace.trace_id == trace_id).first()
    if not trace:
        log.warning("mark_copied", "Trace not found", trace_id=trace_id)
        raise HTTPException(status_code=404, detail="Trace not found")

    trace.is_copied = True
    try:
        db.commit()
        log.info("mark_copied", "Trace marked as copied", trace_id=trace_id)
    except Exception as e:
        db.rollback()
        log.error(
            "mark_copied", "Failed to update trace", error=str(e), trace_id=trace_id
        )
        raise HTTPException(status_code=500, detail="Failed to update trace")

    return {"status": "ok", "message": "Trace marked as copied"}


@router.post("/trace/{trace_id}/comment")
async def update_trace_comment(
    trace_id: str, body: TraceCommentUpdate, db: Session = Depends(get_db)
):
    """
    Add or update a comment for a DSPy trace.
    """
    trace = db.query(DspyTrace).filter(DspyTrace.trace_id == trace_id).first()
    if not trace:
        log.warning("update_comment", "Trace not found", trace_id=trace_id)
        raise HTTPException(status_code=404, detail="Trace not found")

    trace.comment = body.comment
    try:
        db.commit()
        log.info("update_comment", "Trace comment updated", trace_id=trace_id)
    except Exception as e:
        db.rollback()
        log.error(
            "update_comment", "Failed to update trace", error=str(e), trace_id=trace_id
        )
        raise HTTPException(status_code=500, detail="Failed to update trace")

    return {"status": "ok", "message": "Trace comment updated"}
