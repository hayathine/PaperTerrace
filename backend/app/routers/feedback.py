from fastapi import APIRouter, HTTPException, Request

from app.models.log_schemas.schemas import FeedbackData
from app.models.repositories.feedback_repository import FeedbackRepository
from app.schemas.feedback import FeedbackRequest
from common.logger import ServiceLogger

log = ServiceLogger("Feedback")


router = APIRouter(prefix="/feedback", tags=["Feedback"])


@router.post("", summary="汎用的なフィードバックを記録する")
async def submit_feedback(
    req: FeedbackRequest,
    request: Request,
):
    """
    AI生成結果（推薦、要約、レビュー等）に対するユーザーの評価（Good/Bad）を記録する
    """
    current_user_id = getattr(request.state, "user_id", None) or (
        f"guest:{req.session_id}" if req.session_id else "anonymous"
    )

    feedback = FeedbackData(
        session_id=req.session_id,
        user_id=current_user_id,
        target_type=req.target_type,
        target_id=req.target_id,
        trace_id=req.trace_id,
        user_score=req.user_rating,  # user_rating (0/1) を user_score に変換
        user_comment=req.user_comment,
    )
    log.debug(
        "submit",
        "New feedback received",
        type=req.target_type,
        rating=req.user_rating,
        comment=req.user_comment,
    )

    repo = FeedbackRepository()
    try:
        repo.create(feedback)
    except Exception as e:
        log.error("submit", "Failed to save feedback", error=str(e))
        raise HTTPException(status_code=500, detail="Failed to save feedback")

    return {"status": "ok", "message": "Feedback recorded successfully"}
