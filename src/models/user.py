"""
User model for PaperTerrace.
Represents registered users with their profiles.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, EmailStr, Field


class UserVisibility(str, Enum):
    """User profile visibility settings."""

    PUBLIC = "public"
    PRIVATE = "private"


class UserBase(BaseModel):
    """Base user schema with common fields."""

    display_name: str | None = Field(None, max_length=100)
    affiliation: str | None = Field(None, max_length=200, description="所属機関")
    bio: str | None = Field(None, max_length=500, description="自己紹介")
    research_fields: list[str] = Field(default_factory=list, description="研究分野タグ")
    profile_image_url: str | None = None
    is_public: bool = True


class UserCreate(UserBase):
    """Schema for creating a new user."""

    email: EmailStr


class UserUpdate(BaseModel):
    """Schema for updating user profile."""

    display_name: str | None = Field(None, max_length=100)
    affiliation: str | None = Field(None, max_length=200)
    bio: str | None = Field(None, max_length=500)
    research_fields: list[str] | None = None
    profile_image_url: str | None = None
    is_public: bool | None = None


class UserInDB(UserBase):
    """User schema as stored in database."""

    id: str  # Firebase UID
    email: EmailStr
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class UserPublic(BaseModel):
    """Public user profile (visible to other users)."""

    id: str
    display_name: str | None
    affiliation: str | None
    bio: str | None
    research_fields: list[str]
    profile_image_url: str | None
    paper_count: int = 0
    created_at: datetime


class UserStats(BaseModel):
    """User statistics."""

    paper_count: int = 0
    public_paper_count: int = 0
    total_views: int = 0
    total_likes: int = 0
