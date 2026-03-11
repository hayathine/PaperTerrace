from fastapi import APIRouter, Request

from app.domain.services.recommendation_service import RecommendationService
from app.schemas.recommendation import (
    RecommendationGenerateRequest,
    RecommendationGenerateResponse,
    RecommendationRolloutRequest,
    RecommendationSyncRequest,
)


def get_current_user_id(request: Request) -> str:
    return getattr(request.state, "user_id", "anonymous")


router = APIRouter(prefix="/recommendation", tags=["Recommendation"])


@router.post("/sync", summary="セッションの軌跡データを同期する")
async def sync_trajectory(
    req: RecommendationSyncRequest,
    request: Request,
):
    """
    時間経過やセッション終了時、対話中にフロントから定期送信して
    Trajectoryに行動データを追記/作成する
    """
    current_user_id = get_current_user_id(request)
    return RecommendationService.sync_trajectory(req, current_user_id)


@router.post("/rollout", summary="推薦結果の評価（Rollout）を記録する")
async def submit_rollout(
    req: RecommendationRolloutRequest,
    request: Request,
):
    """
    提示された推薦に対するユーザーの評価をRollout（報酬データ）として記録する
    """
    current_user_id = get_current_user_id(request)
    return RecommendationService.submit_rollout(req, current_user_id)


@router.post(
    "/generate",
    response_model=RecommendationGenerateResponse,
    summary="個人化論文を生成して検索する",
)
async def generate_recommendation(
    req: RecommendationGenerateRequest,
    request: Request,
):
    """
    Trajectory履歴とDSPyのRecommendationModuleを用いて推薦論文リストと検索クエリを作成し、
    Semantic Scholarで最新の論文を取得して応答する
    """
    current_user_id = get_current_user_id(request)
    return await RecommendationService.generate_recommendation(req, current_user_id)
