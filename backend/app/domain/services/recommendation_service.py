import json
import time

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.domain.services.paper_acquisition import PaperAcquisitionService
from app.models.orm.recommendation import Feedback
from app.models.repositories.feedback_repository import FeedbackRepository
from app.models.repositories.trajectory_repository import TrajectoryRepository
from app.schemas.recommendation import (
    RecommendationGenerateRequest,
    RecommendationGenerateResponse,
    RecommendationRolloutRequest,
    RecommendationSyncRequest,
)
from common.dspy.config import load_dspy_module_from_gcs, setup_dspy
from common.dspy.modules import RecommendationModule, UserProfileModule
from common.dspy.trace import TraceContext, trace_dspy_call
from common.logger import logger
from redis_provider.provider import RedisService


class RecommendationService:
    _rec_mod = None
    _profile_mod = None

    @classmethod
    def _get_profile_module(cls):
        """Get or initialize the singleton UserProfileModule"""
        if cls._profile_mod is None:
            setup_dspy()
            cls._profile_mod = UserProfileModule()
            # To optionally load an optimized version if it exists:
            # load_dspy_module_from_gcs(cls._profile_mod, "optimized_user_profile.json")
        return cls._profile_mod

    @classmethod
    def _get_recommendation_module(cls):
        """Get or initialize the singleton RecommendationModule"""
        if cls._rec_mod is None:
            setup_dspy()
            cls._rec_mod = RecommendationModule()
            # 保管された最適化済みプロンプトをGCSからロードする（フォールバックあり）
            load_dspy_module_from_gcs(cls._rec_mod, "optimized_recommendation.json")
        return cls._rec_mod

    @staticmethod
    def sync_trajectory(
        req: RecommendationSyncRequest, current_user_id: str, db: Session
    ) -> dict:
        """
        時間経過やセッション終了時、対話中にフロントから定期送信して
        Trajectoryに行動データを追記/作成する。
        ハイブリッド構成: 高頻度な更新はRedisでキャッシュし、
        60分経過またはセッション切れ（明示的な終了等）でマスター(Cloud SQL)に保存する。
        """
        redis_client = RedisService()
        cache_key = f"trajectory:{req.session_id}"

        # 1. 既存データの取得 (Redis -> DBの順)
        cached_data = redis_client.get(cache_key)

        repo = TrajectoryRepository(db)
        trajectory = None

        if cached_data:
            # 辞書からORMライクなオブジェクトを復元するか、辞書として扱う
            # ここではDBから取得したオブジェクトにマージする方針とする
            trajectory = repo.get_by_session_id(req.session_id)
            if not trajectory:
                trajectory = repo.create(current_user_id, req.session_id)

            # Redisからの復元 (辞書)
            if isinstance(cached_data, str):
                import json

                try:
                    cached_data = json.loads(cached_data)
                except Exception:
                    cached_data = {}
            elif isinstance(cached_data, dict):
                pass
            else:
                cached_data = {}
        else:
            trajectory = repo.get_by_session_id(req.session_id)
            if not trajectory:
                trajectory = repo.create(current_user_id, req.session_id)
            # Create dict representation
            cached_data = {
                "paper_id": trajectory.paper_id,
                "paper_title": trajectory.paper_title,
                "paper_abstract": trajectory.paper_abstract,
                "paper_keywords": trajectory.paper_keywords,
                "paper_difficulty": trajectory.paper_difficulty,
                "conversation_history": trajectory.conversation_history,
                "word_clicks": trajectory.word_clicks,
                "session_duration": trajectory.session_duration,
                "clicked_papers": trajectory.clicked_papers,
                "recommended_papers": trajectory.recommended_papers,
                "knowledge_level": trajectory.knowledge_level,
                "interests": trajectory.interests,
                "unknown_concepts": trajectory.unknown_concepts,
                "preferred_direction": trajectory.preferred_direction,
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
            clicks_data = [w.dict() for w in req.word_clicks]
            existing_clicks = cached_data.get("word_clicks") or []
            existing_clicks.extend(clicks_data)
            cached_data["word_clicks"] = existing_clicks
        if req.session_duration is not None:
            cached_data["session_duration"] = req.session_duration

        # 一時保存 (スライディングウィンドウ: 1時間 = 3600秒)
        # アクセスがあるたびに期限が1時間延長される
        SESSION_TIMEOUT = 3600
        redis_client.set(cache_key, cached_data, expire=SESSION_TIMEOUT)

        # 3. マスター(Cloud SQL)への同期判定
        # 2時間(7200秒)経過、またはセッション終了(is_final=True)時に保存。
        last_sync = cached_data.get("last_db_sync", 0)
        current_time = time.time()

        SYNC_INTERVAL = 7200  # 2時間ごとに定期保存

        if (current_time - last_sync) > SYNC_INTERVAL or req.is_final:
            # DBに反映
            trajectory.paper_id = cached_data.get("paper_id")
            trajectory.paper_title = cached_data.get("paper_title")
            trajectory.paper_abstract = cached_data.get("paper_abstract")
            trajectory.paper_keywords = cached_data.get("paper_keywords")
            trajectory.paper_difficulty = cached_data.get("paper_difficulty")
            trajectory.conversation_history = cached_data.get("conversation_history")
            trajectory.word_clicks = cached_data.get("word_clicks")
            trajectory.session_duration = cached_data.get("session_duration")
            trajectory.clicked_papers = cached_data.get("clicked_papers")
            trajectory.recommended_papers = cached_data.get("recommended_papers")
            trajectory.knowledge_level = cached_data.get("knowledge_level")
            trajectory.interests = cached_data.get("interests")
            trajectory.unknown_concepts = cached_data.get("unknown_concepts")
            trajectory.preferred_direction = cached_data.get("preferred_direction")

            repo.save(trajectory)

            # 最終同期時刻を更新して再キャッシュ
            cached_data["last_db_sync"] = current_time
            redis_client.set(cache_key, cached_data, expire=SESSION_TIMEOUT)

            sync_msg = (
                "Database synced (Interval/Final)"
                if not req.is_final
                else "Database synced (Session Closed)"
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
    def submit_rollout(
        req: RecommendationRolloutRequest, current_user_id: str, db: Session
    ) -> dict:
        """
        提示された推薦に対するユーザーの10段階評価（GEPAオプティマイザのMetrics用）を受け取る
        """
        traj_repo = TrajectoryRepository(db)
        fb_repo = FeedbackRepository(db)

        trajectory = traj_repo.get_by_session_id(req.session_id)
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
            target_type="recommendation",  # Default
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

        traj_repo.save(trajectory)
        return {"status": "ok", "message": "Feedback recorded successfully"}

    @staticmethod
    def generate_recommendation(
        req: RecommendationGenerateRequest, current_user_id: str, db: Session
    ) -> RecommendationGenerateResponse:
        """
        Trajectory履歴とDSPyのRecommendationModuleを用いて推薦論文リストと検索クエリを作成し、
        Semantic Scholarで最新の論文を取得して応答する
        """
        repo = TrajectoryRepository(db)

        trajectory = repo.get_by_session_id(req.session_id)

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
            profile_mod = RecommendationService._get_profile_module()

            clicks_str = json.dumps(trajectory.word_clicks or [], ensure_ascii=False)
            profile_res = trace_dspy_call(
                "UserProfileModule",
                "UserProfileEstimation",
                profile_mod,
                {
                    "paper_summary": trajectory.paper_abstract or "",
                    "conversation_history": trajectory.conversation_history or "",
                    "word_clicks": clicks_str,
                },
                context=TraceContext(
                    user_id=current_user_id,
                    session_id=req.session_id,
                    paper_id=trajectory.paper_id if trajectory else None,
                ),
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
            repo.save(trajectory)

        # 論文推薦クエリ生成
        rec_mod = RecommendationService._get_recommendation_module()

        interests_str = (
            ", ".join(interests) if isinstance(interests, list) else str(interests)
        )
        unknowns_str = (
            ", ".join(unknown_concepts)
            if isinstance(unknown_concepts, list)
            else str(unknown_concepts)
        )

        rec_res = trace_dspy_call(
            "RecommendationModule",
            "PaperRecommendation",
            rec_mod,
            {
                "paper_analysis": paper_analysis,
                "knowledge_level": knowledge_level,
                "interests": interests_str,
                "unknown_concepts": unknowns_str,
                "preferred_direction": preferred_direction,
            },
            context=TraceContext(
                user_id=current_user_id,
                session_id=req.session_id,
                paper_id=trajectory.paper_id if trajectory else None,
            ),
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
            repo.save(trajectory)

        return RecommendationGenerateResponse(
            recommendations=final_recs,
            reasoning=rec_res.reasoning
            if hasattr(rec_res, "reasoning")
            else "Generated by AI",
            knowledge_level=knowledge_level,
            search_queries=search_queries,
        )
