from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WordClickEvent(BaseModel):
    word: str
    context: str
    section: str = "Other"
    timestamp: float


class CopyEvent(BaseModel):
    text: str
    context: Optional[str] = None
    target_type: str = "text"  # "text", "translation", "summary"
    timestamp: float


class RecommendationSyncRequest(BaseModel):
    session_id: str
    paper_id: Optional[str] = None
    paper_title: Optional[str] = None
    paper_abstract: Optional[str] = None
    paper_keywords: Optional[List[str]] = None
    paper_difficulty: Optional[str] = None
    conversation_history: Optional[str] = None
    word_clicks: Optional[List[WordClickEvent]] = None
    copy_events: Optional[List[CopyEvent]] = None
    session_duration: Optional[float] = None
    is_final: bool = False


class RecommendationRolloutRequest(BaseModel):
    session_id: str
    user_score: int = Field(..., ge=1, le=10)
    user_comment: Optional[str] = None
    clicked_paper: Optional[str] = None
    followed_up_query: Optional[bool] = None


class RecommendationGenerateRequest(BaseModel):
    session_id: str
    user_query: Optional[str] = None  # ユーザーが希望する論文の種類（任意）


class RecommendationGenerateResponse(BaseModel):
    recommendations: List[Dict[str, Any]]
    reasoning: str
    knowledge_level: str
    search_queries: List[str]
    trace_id: Optional[str] = None
