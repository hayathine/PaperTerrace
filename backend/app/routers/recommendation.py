import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.domain.dspy.config import load_dspy_module_from_gcs, setup_dspy
from app.domain.dspy.modules import RecommendationModule, UserProfileModule
from app.domain.services.paper_acquisition import PaperAcquisitionService
from app.models.orm.recommendation import Feedback, Trajectory
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
    trajectory = (
        db.query(Trajectory).filter(Trajectory.session_id == req.session_id).first()
    )

    if not trajectory:
        trajectory = Trajectory(
            user_id=current_user_id,
            session_id=req.session_id,
        )
        db.add(trajectory)

    # Partial updates
    if req.paper_id:
        trajectory.paper_id = req.paper_id
    if req.paper_title:
        trajectory.paper_title = req.paper_title
    if req.paper_abstract:
        trajectory.paper_abstract = req.paper_abstract
    if req.paper_keywords is not None:
        trajectory.paper_keywords = req.paper_keywords
    if req.paper_difficulty:
        trajectory.paper_difficulty = req.paper_difficulty
    if req.conversation_history is not None:
        trajectory.conversation_history = req.conversation_history
    if req.word_clicks is not None:
        # Pydantic lists to dict parsing
        clicks_data = [w.dict() for w in req.word_clicks]
        existing_clicks = trajectory.word_clicks or []
        existing_clicks.extend(clicks_data)
        trajectory.word_clicks = existing_clicks
    if req.session_duration is not None:
        trajectory.session_duration = req.session_duration

    db.commit()
    return {"status": "ok", "message": "Trajectory synced"}


@router.post("/feedback", summary="ユーザー評価を記録する")
async def submit_feedback(
    req: RecommendationFeedbackRequest,
    db: Session = Depends(get_db),
    current_user_id: str = Depends(lambda r: getattr(r.state, "user_id", "anonymous")),
):
    """
    提示された推薦に対するユーザーの10段階評価（GEPAオプティマイザのMetrics用）を受け取る
    """
    trajectory = (
        db.query(Trajectory).filter(Trajectory.session_id == req.session_id).first()
    )
    if not trajectory:
        raise HTTPException(
            status_code=404, detail="Session not found to attach feedback"
        )

    # Record feedback
    feedback = Feedback(
        session_id=req.session_id,
        user_id=current_user_id,
        user_score=req.user_score,
        user_comment=req.user_comment,
    )
    db.add(feedback)

    # Update Trajectory for offline analysis ease
    if req.clicked_paper:
        clicked_list = trajectory.clicked_papers or []
        if req.clicked_paper not in clicked_list:
            clicked_list.append(req.clicked_paper)
            trajectory.clicked_papers = clicked_list

    if req.followed_up_query is not None:
        trajectory.followed_up_query = req.followed_up_query

    db.commit()
    return {"status": "ok", "message": "Feedback recorded successfully"}


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
    setup_dspy()

    trajectory = (
        db.query(Trajectory).filter(Trajectory.session_id == req.session_id).first()
    )

    # 履歴がないか空白の場合は、冷え切り状態 (Cold Start) のデフォルト値を渡す
    if not trajectory or not trajectory.conversation_history:
        knowledge_level = "初級"
        interests = (
            ["machine learning", "deep learning"]
            if not trajectory
            else (trajectory.paper_keywords or [])
        )
        unknown_concepts = []
        preferred_direction = "基礎"
        paper_analysis = (
            trajectory.paper_abstract
            if trajectory and trajectory.paper_abstract
            else "No paper selected yet."
        )
    else:
        # プロファイル推定
        profile_mod = UserProfileModule()
        # To optionally load an optimized version if it exists:
        # load_dspy_module_from_gcs(profile_mod, "optimized_user_profile.json")

        clicks_str = json.dumps(trajectory.word_clicks or [], ensure_ascii=False)
        profile_res = profile_mod(
            paper_summary=trajectory.paper_abstract or "",
            conversation_history=trajectory.conversation_history or "",
            word_clicks=clicks_str,
        )
        knowledge_level = profile_res.knowledge_level
        interests = profile_res.interests
        unknown_concepts = profile_res.unknown_concepts
        preferred_direction = profile_res.preferred_direction
        paper_analysis = f"{trajectory.paper_title}\n{trajectory.paper_abstract}"

        # 軌跡にもプロファイルを更新しておく
        trajectory.knowledge_level = knowledge_level
        trajectory.interests = interests
        trajectory.unknown_concepts = unknown_concepts
        trajectory.preferred_direction = preferred_direction
        db.commit()

    # 論文推薦クエリ生成
    rec_mod = RecommendationModule()

    # 5. 保管された最適化済みプロンプトをGCSからロードする（フォールバックあり）
    load_dspy_module_from_gcs(rec_mod, "optimized_recommendation.json")

    interests_str = (
        ", ".join(interests) if isinstance(interests, list) else str(interests)
    )
    unknowns_str = (
        ", ".join(unknown_concepts)
        if isinstance(unknown_concepts, list)
        else str(unknown_concepts)
    )

    rec_res = rec_mod(
        paper_analysis=paper_analysis,
        knowledge_level=knowledge_level,
        interests=interests_str,
        unknown_concepts=unknowns_str,
        preferred_direction=preferred_direction,
    )

    # Semaphore Scholar API を使って検索を実行
    search_queries = rec_res.search_queries
    paper_acq = PaperAcquisitionService()

    fetched_papers = []
    # 生成されたクエリの中からいくつかピックアップして検索
    for q in search_queries[:3]:
        # limit=3 で関連論文情報を取得
        items = paper_acq.search_papers(query=q, limit=3)
        for it in items:
            # deduplicate simple naive check
            if it.get("title") not in [p.get("title") for p in fetched_papers]:
                fetched_papers.append(it)

    # If no papers found via standard search, fallback to returning the textual descriptions directly
    if not fetched_papers:
        # convert dspy plain text recommendations into dict
        fetched_papers = [
            {"title": r, "abstract": "Detail unavailable", "url": None}
            for r in rec_res.recommendations
        ]

    # Pick top 5 at most
    final_recs = fetched_papers[:5]

    # Optional: Log recommended_papers to trajectory
    if trajectory:
        trajectory.recommended_papers = [p.get("title") for p in final_recs]
        db.commit()

    return RecommendationGenerateResponse(
        recommendations=final_recs,
        reasoning=rec_res.reasoning
        if hasattr(rec_res, "reasoning")
        else "Generated by AI",
        knowledge_level=knowledge_level,
        search_queries=search_queries,
    )
