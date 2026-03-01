from typing import Optional

from pydantic import BaseModel, EmailStr


class ContactRequest(BaseModel):
    """ホームページからの要望・フィードバックのリクエストスキーマ。"""

    name: Optional[str] = None
    email: Optional[EmailStr] = None
    message: str
