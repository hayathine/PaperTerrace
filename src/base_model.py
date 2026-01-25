import uuid6
from pydantic import BaseModel, Field


class User(BaseModel):
    # 外部に公開するIDは UUID v7 を使用
    user_id: str = Field(default_factory=lambda: str(uuid6.uuid7()))
    nickname: str
    birthday: str  # ISOフォーマットの文字列（例：YYYY-MM-DD）


class History(BaseModel):
    word: str
    explain: str
    source: str
    created_at: str  # ISOフォーマットの文字列
    user_id: str
