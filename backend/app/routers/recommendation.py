from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain.services.recommendation_service import RecommendationService
from app.schemas.recommendation import (
    RecommendationFeedbackRequest,
    RecommendationGenerateRequest,
    RecommendationGenerateResponse,
    RecommendationSyncRequest,
)

router = APIRouter(prefix="/recommendation", tags=["Recommendation"])


@router.post("/sync", summary="セッションの軌跡データを同期する")
async def sync_trajectory(
    req: RecommendationSyncRequest,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(lambda r: getattr(r.state, "user_id", "anonymous")),
):
    """
    時間経過やセッション終了時、対話中にフロントから定期送信して
    Trajectoryに行動データを追記/作成する
    """
    return RecommendationService.sync_trajectory(req, current_user_id, db)


@router.post("/feedback", summary="ユーザー評価を記録する")
async def submit_feedback(
    req: RecommendationFeedbackRequest,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(lambda r: getattr(r.state, "user_id", "anonymous")),
):
    """
    提示された推薦に対するユーザーの10段階評価（GEPAオプティマイザのMetrics用）を受け取る
    """
    return RecommendationService.submit_feedback(req, current_user_id, db)


@router.post(
    "/generate",
    response_model=RecommendationGenerateResponse,
    summary="個人化論文を生成して検索する",
)
async def generate_recommendation(
    req: RecommendationGenerateRequest, db: Session = Depends(get_db)
):
    """
    Trajectory履歴とDSPyのRecommendationModuleを用いて推薦論文リストと検索クエリを作成し、
    Semantic Scholarで最新の論文を取得して応答する
    """
    return RecommendationService.generate_recommendation(req, db)
