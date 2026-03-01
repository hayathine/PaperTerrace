"""
Routers package for PaperTerrace.
Contains FastAPI routers for different API endpoints.
"""

from app.routers.analysis import router as analysis_router
from app.routers.auth import router as auth_router
from app.routers.chat import router as chat_router
from app.routers.contact import router as contact_router
from app.routers.feedback import router as feedback_router
from app.routers.figures import router as figures_router
from app.routers.note import router as note_router
from app.routers.papers import router as papers_router
from app.routers.pdf import router as pdf_router
from app.routers.recommendation import router as recommendation_router
from app.routers.stamps import router as stamps_router
from app.routers.translation import router as translation_router
from app.routers.upload import router as upload_router
from app.routers.users import router as users_router

__all__ = [
    "auth_router",
    "users_router",
    "pdf_router",
    "translation_router",
    "chat_router",
    "analysis_router",
    "figures_router",
    "note_router",
    "papers_router",
    "stamps_router",
    "upload_router",
    "recommendation_router",
    "feedback_router",
    "contact_router",
]
