"""
PaperTerrace - AI-powered paper reading assistant
Main application entry point.
"""

import contextlib
import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.cors import CORSMiddleware

from .routers import (
    analysis_router,
    auth_router,
    chat_router,
    explore_router,
    figures_router,
    note_router,
    papers_router,
    pdf_router,
    stamps_router,
    tasks_router,
    translation_router,
    upload_router,
    users_router,
)

# Load environment variables
load_dotenv()

# Firebase Config for Frontend
FIREBASE_CONFIG = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "measurementId": os.getenv("FIREBASE_MEASUREMENT_ID"),
}


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI.
    Handles startup and shutdown events.
    """
    from src.logger import configure_logging, logger

    # Re-configure logging to ensure it survives uvicorn's setup
    configure_logging()

    async def _prewarm_models():
        try:
            from src.domain.services.local_translator import get_local_translator
            from src.domain.services.nlp_service import NLPService

            # Prewarm Local Translator (M2M100)
            lt = get_local_translator()
            await lt.prewarm()

            # Prewarm NLP (spaCy) - internal buffers
            NLPService.lemmatize("warmup")
            logger.info("Pre-warmed NLP (spaCy)")

        except Exception as e:
            logger.warning(f"Failed to pre-warm models: {e}")

    logger.info("Starting up...")
    try:
        # Run Alembic migrations
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config("alembic.ini")
        # Ensure alembic uses the correct directory if we're not in root (though usually we are)
        command.upgrade(alembic_cfg, "head")
        logger.info("Database migrations applied successfully")

        # Pre-warm models before server starts (Blocking)
        logger.info("Pre-warming models before accepting requests...")
        await _prewarm_models()
        logger.info("All models loaded. Server is ready.")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")

    yield

    logger.info("Shutting down...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="PaperTerrace",
    description="AI-powered paper reading assistant",
    version="1.0.0",
    lifespan=lifespan,
)

# Templates and static files
templates = Jinja2Templates(directory="src/templates")
app.mount("/static", StaticFiles(directory="src/static"), name="static")

# CORS configuration for React development
app.add_middleware(
    CORSMiddleware,  # type: ignore[arg-type]
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post("/api/debug/init-db")
async def init_db_manual():
    """Manual trigger for database initialization."""
    from src.providers import get_storage_provider

    try:
        storage = get_storage_provider()
        if hasattr(storage, "init_tables"):
            storage.init_tables()
            return {"status": "ok", "message": "Tables initialized"}
        return {"status": "skipped", "message": "Storage provider does not support init_tables"}
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})


# ============================================================================
# Include all routers
# ============================================================================

# Auth & Users
app.include_router(auth_router)
app.include_router(users_router)

# Grouped routers
app.include_router(stamps_router)
app.include_router(tasks_router)
app.include_router(translation_router)
app.include_router(explore_router)
app.include_router(chat_router)
app.include_router(note_router)
app.include_router(papers_router)
app.include_router(upload_router)

# PDF Analysis & Streaming
app.include_router(pdf_router)

# Analysis Features
app.include_router(analysis_router)
app.include_router(figures_router)


# ============================================================================
# Main Page
# ============================================================================


# Serve React assets
# Determine dist directory (Docker vs Local)
dist_dir = "src/static/dist"
if not os.path.exists(dist_dir) and os.path.exists("frontend/dist"):
    dist_dir = "frontend/dist"

if os.path.exists(dist_dir):
    # Mount assets folder if it exists
    assets_dir = os.path.join(dist_dir, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="assets")


# ... routers ...

# ============================================================================
# Main Page & API
# ============================================================================


@app.get("/api/health")
async def health_check():
    return {"status": "ok"}


@app.get("/api/config")
async def get_config():
    """Returns configuration for the frontend."""
    return JSONResponse(content={"firebase_config": FIREBASE_CONFIG})


@app.get("/{full_path:path}", response_class=HTMLResponse)
async def serve_react_app(request: Request, full_path: str):
    # Allow other defined routes (like /papers, /chat) to handle their requests by returning None here?
    # No, FastAPI routing doesn't work that way. This is a catch-all.
    # But since it's defined LAST (after routers), it only catches what routers didn't catch.
    # However, include_router adds routes.
    # So if I put this at the very end, it catches 404s.

    # Check if index.html exists
    index_file = os.path.join(dist_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)

    # Fallback to old template if React build not found (or for intentionally unhandled routes?)
    # For now, just render index.html (old one) if React not found.
    return templates.TemplateResponse(
        "index.html", {"request": request, "firebase_config": FIREBASE_CONFIG}
    )
