"""
Models package for PaperTerrace.
Contains Pydantic models for API request/response validation.
"""

from .paper import (
    PaperBase,
    PaperCreate,
    PaperDetail,
    PaperInDB,
    PaperListResponse,
    PaperPublic,
    PaperUpdate,
    PaperVisibility,
)
from .user import (
    UserBase,
    UserCreate,
    UserInDB,
    UserPublic,
    UserStats,
    UserUpdate,
    UserVisibility,
)

__all__ = [
    # User models
    "UserBase",
    "UserCreate",
    "UserUpdate",
    "UserInDB",
    "UserPublic",
    "UserStats",
    "UserVisibility",
    # Paper models
    "PaperBase",
    "PaperCreate",
    "PaperUpdate",
    "PaperInDB",
    "PaperPublic",
    "PaperDetail",
    "PaperListResponse",
    "PaperVisibility",
]
