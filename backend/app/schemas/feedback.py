from typing import Optional

from pydantic import BaseModel


class FeedbackRequest(BaseModel):
    session_id: str
    target_type: str  # "recommendation", "summary", "critique", "related_papers", etc.
    target_id: Optional[str] = None
    user_score: int  # 1 for Good, 0 for Bad
    user_comment: Optional[str] = None
