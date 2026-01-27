"""
Paper model for PaperTerrace.
Extended to support social features like visibility and ownership.
"""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class PaperVisibility(str, Enum):
    """Paper visibility settings."""

    PRIVATE = "private"  # Only visible to owner
    PUBLIC = "public"  # Visible to everyone, listed in explore
    UNLISTED = "unlisted"  # Accessible via URL, but not listed


class PaperBase(BaseModel):
    """Base paper schema with common fields."""

    title: str = Field(..., max_length=500)
    authors: str | None = None
    abstract: str | None = None
    tags: list[str] = Field(default_factory=list)


class PaperCreate(PaperBase):
    """Schema for creating a new paper."""

    visibility: PaperVisibility = PaperVisibility.PRIVATE


class PaperUpdate(BaseModel):
    """Schema for updating paper metadata."""

    title: str | None = Field(None, max_length=500)
    authors: str | None = None
    abstract: str | None = None
    tags: list[str] | None = None
    visibility: PaperVisibility | None = None


class PaperInDB(PaperBase):
    """Paper schema as stored in database."""

    id: str
    owner_id: str | None = None  # Firebase UID, None for legacy papers
    visibility: PaperVisibility = PaperVisibility.PRIVATE
    pdf_url: str | None = None
    ai_summary: str | None = None
    full_text: str | None = None
    view_count: int = 0
    like_count: int = 0
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class PaperPublic(BaseModel):
    """Public paper view (for explore page)."""

    id: str
    title: str
    authors: str | None
    abstract: str | None
    tags: list[str]
    visibility: PaperVisibility
    view_count: int = 0
    like_count: int = 0
    created_at: datetime
    # Owner info (denormalized for efficiency)
    owner_id: str | None = None
    owner_name: str | None = None
    owner_image_url: str | None = None


class PaperDetail(PaperPublic):
    """Detailed paper view (for paper page)."""

    ai_summary: str | None = None
    full_text: str | None = None
    is_liked: bool = False  # Current user's like status
    is_owner: bool = False  # Whether current user owns this paper


class PaperListResponse(BaseModel):
    """Response for paper list endpoints."""

    papers: list[PaperPublic]
    total: int
    page: int
    per_page: int
    has_more: bool
