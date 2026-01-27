"""
Routers package for PaperTerrace.
Contains FastAPI routers for different API endpoints.
"""

from .analysis import router as analysis_router
from .auth import router as auth_router
from .chat import router as chat_router
from .explore import router as explore_router
from .note import router as note_router
from .papers import router as papers_router
from .pdf import router as pdf_router
from .stamps import router as stamps_router
from .translation import router as translation_router
from .users import router as users_router

__all__ = [
    "auth_router",
    "users_router",
    "explore_router",
    "pdf_router",
    "translation_router",
    "chat_router",
    "analysis_router",
    "note_router",
    "papers_router",
    "stamps_router",
]
