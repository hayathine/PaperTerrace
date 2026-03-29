import json
import time

from fastapi import HTTPException

from app.domain.services.paper_acquisition import PaperAcquisitionService
from app.models.log_schemas.schemas import FeedbackData, TrajectoryData
from app.models.repositories.feedback_repository import FeedbackRepository
from app.models.repositories.trajectory_repository import TrajectoryRepository
from app.schemas.recommendation import (
    RecommendationGenerateRequest,
    RecommendationGenerateResponse,
    RecommendationRolloutRequest,
    RecommendationSyncRequest,
)
from common.dspy_utils.config import load_dspy_module_from_gcs, setup_dspy
from common.dspy_utils.modules import RecommendationModule, UserPersonaModule
from common.dspy_utils.trace import TraceContext, trace_dspy_call
from common.logger import logger
from redis_provider.provider import RedisService


class RecommendationService:
    _rec_mod = None
    _profile_mod = None

    @classmethod
    def _get_profile_module(cls):
        """Get or initialize the singleton UserPersonaModule"""
        if cls._profile_mod is None:
            setup_dspy()
            cls._profile_mod = UserPersonaModule()
        return cls._profile_mod

    @classmethod
    def _get_recommendation_module(cls):
        """Get or initialize the singleton RecommendationModule"""
        if cls._rec_mod is None:
            setup_dspy()
            cls._rec_mod = RecommendationModule()
            load_dspy_module_from_gcs(cls._rec_mod, "optimized_recommendation.json")
        return cls._rec_mod

    @staticmethod
    def sync_trajectory(req: RecommendationSyncRequest, current_user_id: str) -> dict:
        """
        時間経過やセッション終了時、対話中にフロントから定期送信して
        Trajectoryに行動データを追記/作成する。
        ハイブリッド構成: 高頻度な更新はRedisでキャッシュし、
        60分経過またはセッション切れ（明示的な終了等）で PostgreSQL に保存する。
        """
        redis_client = RedisService()
        cache_key = f"trajectory:{req.session_id}"

        # 1. 既存データの取得 (Redis → PostgreSQLの順)
        cached_data = redis_client.get(cache_key)

        if cached_data:
            if isinstance(cached_data, str):
                try:
                    cached_data = json.loads(cached_data)
                except Exception:
                    cached_data = {}
            elif not isinstance(cached_data, dict):
                cached_data = {}
        else:
            # No Redis data - check PostgreSQL for historical data
            repo = TrajectoryRepository()
            trajectory = repo._query_pg(req.session_id)
            if trajectory:
                cached_data = trajectory.to_cache_dict()
            else:
                cached_data = {
                    "user_id": current_user_id,
                    "last_db_sync": time.time(),
                }

        # 2. Redis上のデータを更新
        if req.paper_id:
            cached_data["paper_id"] = req.paper_id
        if req.paper_title:
            cached_data["paper_title"] = req.paper_title
        if req.paper_abstract:
            cached_data["paper_abstract"] = req.paper_abstract
        if req.paper_keywords is not None:
            cached_data["paper_keywords"] = req.paper_keywords
        if req.paper_difficulty:
            cached_data["paper_difficulty"] = req.paper_difficulty
        if req.conversation_history is not None:
            cached_data["conversation_history"] = req.conversation_history
        if req.word_clicks is not None:
            clicks_data = [w.model_dump() for w in req.word_clicks]
            existing_clicks = cached_data.get("word_clicks") or []
            existing_clicks.extend(clicks_data)
            cached_data["word_clicks"] = existing_clicks
        if req.copy_events is not None:
            copy_data = [c.model_dump() for c in req.copy_events]
            existing_copies = cached_data.get("copy_events") or []
            existing_copies.extend(copy_data)
            cached_data["copy_events"] = existing_copies
        if req.session_duration is not None:
            cached_data["session_duration"] = req.session_duration

        # 一時保存 (スライディングウィンドウ: 1時間 = 3600秒)
        SESSION_TIMEOUT = 3600
        redis_client.set(cache_key, cached_data, expire=SESSION_TIMEOUT)

        # 3. PostgreSQLへの同期判定
        last_sync = cached_data.get("last_db_sync", 0)
        current_time = time.time()
        SYNC_INTERVAL = 7200  # 2時間ごとに定期保存

        if (current_time - last_sync) > SYNC_INTERVAL or req.is_final:
            # PostgreSQL に反映
            repo = TrajectoryRepository()
            trajectory_data = TrajectoryData(
                session_id=req.session_id,
                user_id=current_user_id,
                paper_id=cached_data.get("paper_id"),
                paper_title=cached_data.get("paper_title"),
                paper_abstract=cached_data.get("paper_abstract"),
                paper_keywords=cached_data.get("paper_keywords"),
                paper_difficulty=cached_data.get("paper_difficulty"),
                conversation_history=cached_data.get("conversation_history"),
                word_clicks=cached_data.get("word_clicks"),
                copy_events=cached_data.get("copy_events"),
                session_duration=cached_data.get("session_duration"),
                knowledge_level=cached_data.get("knowledge_level"),
                interests=cached_data.get("interests"),
                unknown_concepts=cached_data.get("unknown_concepts"),
                preferred_direction=cached_data.get("preferred_direction"),
                clicked_papers=cached_data.get("clicked_papers"),
                recommended_papers=cached_data.get("recommended_papers"),
            )
            repo.upsert(trajectory_data)

            # 最終同期時刻を更新して再キャッシュ
            cached_data["last_db_sync"] = current_time
            redis_client.set(cache_key, cached_data, expire=SESSION_TIMEOUT)

            sync_msg = (
                "PostgreSQL synced (Interval/Final)"
                if not req.is_final
                else "PostgreSQL synced (Session Closed)"
            )
            return {
                "status": "ok",
                "message": f"Trajectory synced to Redis AND {sync_msg}",
            }

        return {
            "status": "ok",
            "message": "Trajectory synced to Redis (Memory). Session extended by 1 hour.",
        }

    @staticmethod
    def submit_rollout(req: RecommendationRolloutRequest, current_user_id: str) -> dict:
        """
        提示された推薦に対するユーザーの10段階評価（GEPAオプティマイザのMetrics用）を受け取る
        """
        traj_repo = TrajectoryRepository()
        fb_repo = FeedbackRepository()

        trajectory = traj_repo.get_by_session_id(req.session_id)
        if not trajectory:
            raise HTTPException(
                status_code=404, detail="Session not found to attach feedback"
            )

        # Record feedback in PostgreSQL
        feedback = FeedbackData(
            session_id=req.session_id,
            user_id=current_user_id,
            user_score=req.user_score,
            user_comment=req.user_comment,
            target_type="recommendation",
        )
        logger.debug(
            f"[Recommendation] New Rollout: score={req.user_score}, comment={req.user_comment}, session={req.session_id}"
        )
        fb_repo.create(feedback)

        # Update Trajectory for offline analysis ease
        if req.clicked_paper:
            clicked_list = trajectory.clicked_papers or []
            if req.clicked_paper not in clicked_list:
                clicked_list.append(req.clicked_paper)
                trajectory.clicked_papers = clicked_list

        if req.followed_up_query is not None:
            trajectory.followed_up_query = req.followed_up_query

        traj_repo.upsert(trajectory)
        return {"status": "ok", "message": "Feedback recorded successfully"}

    @staticmethod
    async def generate_recommendation(
        req: RecommendationGenerateRequest, current_user_id: str, db=None
    ) -> RecommendationGenerateResponse:
        """
        Trajectory履歴とDSPyのRecommendationModuleを用いて推薦論文リストと検索クエリを作成し、
        Semantic Scholarで最新の論文を取得して応答する
        """
        repo = TrajectoryRepository()
        trajectory = repo.get_by_session_id(req.session_id)

        # 履歴がないか空白の場合は、冷え切り状態 (Cold Start)
        if not trajectory or not trajectory.conversation_history:
            user_persona = f"Interested in: {', '.join(trajectory.paper_keywords or []) if trajectory else 'machine learning'}. Prefers fundamentals."
            paper_analysis = (
                trajectory.paper_abstract
                if trajectory and trajectory.paper_abstract
                else "No paper selected yet."
            )
        else:
            # プロファイル推定
            profile_mod = RecommendationService._get_profile_module()

            clicks_str = json.dumps(trajectory.word_clicks or [], ensure_ascii=False)
            profile_res, trace_id = await trace_dspy_call(
                "UserPersonaModule",
                "BuildDecisionProfile",
                profile_mod,
                {
                    "behavior_logs": clicks_str,
                    "current_logs": trajectory.conversation_history or "",
                    "user_feedback": "",  # TODO: 将来的にはフィードバックも活用
                },
                context=TraceContext(
                    user_id=current_user_id,
                    session_id=req.session_id,
                    paper_id=trajectory.paper_id if trajectory else None,
                ),
            )
            user_persona = profile_res.user_persona
            paper_analysis = f"{trajectory.paper_title}\n{trajectory.paper_abstract}"

            # 軌跡にもプロファイルを更新しておく（後方互換性と分析用）
            trajectory.knowledge_level = "Extracted"  # 以前の構造化フィールドは固定値へ
            repo.upsert(trajectory)

        # ユーザーの具体的なリクエストがあれば persona に追記
        if req.user_query:
            user_persona = f"{user_persona}\n\nUser's specific request: {req.user_query}"

        # 論文推薦クエリ生成
        rec_mod = RecommendationService._get_recommendation_module()

        rec_res, trace_id = await trace_dspy_call(
            "RecommendationModule",
            "PaperRecommendation",
            rec_mod,
            {
                "paper_analysis": paper_analysis,
                "user_persona": user_persona,
                "lang_name": "en",
            },
            context=TraceContext(
                user_id=current_user_id,
                session_id=req.session_id,
                paper_id=trajectory.paper_id if trajectory else None,
            ),
        )

        # Semantic Scholar API を使って検索を実行
        search_queries = rec_res.search_queries
        paper_acq = PaperAcquisitionService()

        fetched_papers = []
        for q in search_queries[:3]:
            items = paper_acq.search_papers(query=q, limit=3)
            for it in items:
                if it.get("title") not in [p.get("title") for p in fetched_papers]:
                    fetched_papers.append(it)

        if not fetched_papers:
            fetched_papers = [
                {"title": r, "abstract": "Detail unavailable", "url": None}
                for r in rec_res.recommendations
            ]

        final_recs = fetched_papers[:5]

        # Log recommended_papers to trajectory
        if trajectory:
            trajectory.recommended_papers = [p.get("title") for p in final_recs]
            repo.upsert(trajectory)

        return RecommendationGenerateResponse(
            recommendations=final_recs,
            reasoning=rec_res.reasoning
            if hasattr(rec_res, "reasoning")
            else "Generated by AI",
            knowledge_level="Analyzed",  # 構造化フィールドからペルソナ抽出へ移行したため固定値
            search_queries=search_queries,
            trace_id=trace_id,
        )
