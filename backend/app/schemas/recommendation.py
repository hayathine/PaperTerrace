from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class WordClickEvent(BaseModel):
    word: str
    context: str
    section: str = "Other"
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
    session_duration: Optional[float] = None
    is_final: bool = False


class RecommendationFeedbackRequest(BaseModel):
    session_id: str
    user_score: int = Field(..., ge=1, le=10)
    user_comment: Optional[str] = None
    clicked_paper: Optional[str] = None
    followed_up_query: Optional[bool] = None


class RecommendationGenerateRequest(BaseModel):
    session_id: str


class RecommendationGenerateResponse(BaseModel):
    recommendations: List[Dict[str, Any]]
    reasoning: str
    knowledge_level: str
    search_queries: List[str]
