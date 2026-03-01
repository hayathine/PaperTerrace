from pydantic import BaseModel, EmailStr


class ContactRequest(BaseModel):
    """ホームページからの要望・フィードバックのリクエストスキーマ。"""

    name: str
    email: EmailStr
    message: str
