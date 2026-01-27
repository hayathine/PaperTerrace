"""
Routers package for PaperTerrace.
Contains FastAPI routers for different API endpoints.
"""

from .auth import router as auth_router
from .explore import router as explore_router
from .users import router as users_router

__all__ = [
    "auth_router",
    "users_router",
    "explore_router",
]
