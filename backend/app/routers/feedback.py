from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.orm.recommendation import Feedback, Trajectory
from app.schemas.feedback import FeedbackRequest
from common.logger import logger

router = APIRouter(prefix="/feedback", tags=["Feedback"])


def get_current_user_id(request: Request) -> str:
    return getattr(request.state, "user_id", "anonymous")


@router.post("", summary="汎用的なフィードバックを記録する")
async def submit_feedback(
    req: FeedbackRequest,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(get_current_user_id),
):
    """
    AI生成結果（推薦、要約、レビュー等）に対するユーザーの評価（Good/Bad）を記録する
    """
    # Record feedback
    feedback = Feedback(
        session_id=req.session_id,
        user_id=current_user_id,
        target_type=req.target_type,
        target_id=req.target_id,
        user_score=req.user_score,  # 1 for Good, 0 for Bad
        user_comment=req.user_comment,
    )
    db.add(feedback)

    # If it's a recommendation and we have a specific paper clicked, update trajectory
    if req.target_type == "recommendation" and req.target_id:
        trajectory = (
            db.query(Trajectory).filter(Trajectory.session_id == req.session_id).first()
        )
        if trajectory:
            clicked_list = trajectory.clicked_papers or []
            if req.target_id not in clicked_list:
                clicked_list.append(req.target_id)
                trajectory.clicked_papers = clicked_list

    try:
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to save feedback: {e}")
        raise HTTPException(status_code=500, detail="Failed to save feedback")

    return {"status": "ok", "message": "Feedback recorded successfully"}
