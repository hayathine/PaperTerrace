from typing import Optional

from pydantic import BaseModel, Field


class ClientErrorRequest(BaseModel):
    """フロントエンドから送信されるエラーログのリクエストスキーマ。"""

    message: str = Field(..., max_length=2000)
    component: str = Field(..., max_length=200)
    operation: str = Field(..., max_length=200)
    error_name: Optional[str] = Field(None, max_length=200)
    stack: Optional[str] = Field(None, max_length=10000)
    context: Optional[dict] = None
    url: Optional[str] = Field(None, max_length=2000)
    user_agent: Optional[str] = Field(None, max_length=500)
