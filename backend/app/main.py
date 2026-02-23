"""
PaperTerrace - AI-powered paper reading assistant
Main application entry point.
"""

import contextlib
import os
import re
import time
import traceback
from datetime import datetime

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.cors import CORSMiddleware

from app.routers import (
    analysis_router,
    auth_router,
    chat_router,
    explore_router,
    figures_router,
    note_router,
    papers_router,
    pdf_router,
    stamps_router,
    translation_router,
    upload_router,
    users_router,
)
from common.logger import configure_logging, logger

# Load environment variables from secrets directory
load_dotenv("secrets/.env")

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
    # Re-configure logging to ensure it survives uvicorn's setup if needed
    configure_logging()

    async def _prewarm_models():
        try:
            from app.domain.services.local_translator import get_local_translator
            from app.domain.services.nlp_service import NLPService

            # Prewarm ServiceB (推論サービス)
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


# CORS configuration for React development & production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://paperterrace.page",
        "https://www.paperterrace.page",
    ],
    allow_origin_regex=r"https://.*\.(paperterrace\.page|pages\.dev)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class OriginCheckMiddleware(BaseHTTPMiddleware):
    """
    Middleware to restrict API access to authorized frontend origins.
    Rejects requests (403) from unknown origins or direct access (curl/browser URL bar)
    to protected API endpoints.
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # 1. Allow public/system endpoints
        if path in ["/", "/api/health", "/docs", "/openapi.json", "/api/config"]:
            return await call_next(request)

        # 2. Allow CORS preflight requests (handled by CORSMiddleware)
        if request.method == "OPTIONS":
            return await call_next(request)

        origin = request.headers.get("origin")
        referer = request.headers.get("referer")

        # List of explicitly allowed origins
        allowed_origins = [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "https://paperterrace.page",
            "https://www.paperterrace.page",
        ]

        # Regex for dynamic subdomains (e.g., branch previews on pages.dev)
        pattern = re.compile(r"https://.*\.(paperterrace\.page|pages\.dev)")

        def is_authorized(url: str | None) -> bool:
            if not url:
                return False
            # Check prefix for simple matching
            if any(url.startswith(o) for o in allowed_origins):
                return True
            # Regex match for domain patterns
            if pattern.match(url):
                return True
            return False

        # Allow internal TestClient requests
        if request.client and request.client.host == "testclient":
            return await call_next(request)

        # 3. Deny if neither Origin nor Referer matches the authorized list
        if not (is_authorized(origin) or is_authorized(referer)):
            logger.warning(
                "unauthorized_access_attempt",
                path=path,
                origin=origin,
                referer=referer,
                client=request.client.host if request.client else "unknown",
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "Forbidden",
                    "message": "Access denied. This API is only accessible from the PaperTerrace frontend.",
                },
            )

        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log incoming requests and their responses.
    Includes success, failure, and execution duration.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log request start
        logger.info(
            "request_started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_host=request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log request completion
            logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )
            return response
        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                "request_failed",
                method=request.method,
                path=request.url.path,
                error=str(e),
                error_type=type(e).__name__,
                duration_ms=round(duration * 1000, 2),
            )
            logger.error(traceback.format_exc())
            return JSONResponse(
                status_code=500,
                content={"error": "Internal Server Error", "message": str(e)},
            )


app.add_middleware(OriginCheckMiddleware)
app.add_middleware(LoggingMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):

    logger.error(f"Global exception: {request.method} {request.url.path}")
    logger.error(traceback.format_exc())
    return JSONResponse(
        status_code=500, content={"error": "Internal Server Error", "message": str(exc)}
    )


@app.post("/api/debug/init-db")
async def init_db_manual():
    """Manual trigger for database initialization."""
    from app.providers import get_storage_provider

    try:
        storage = get_storage_provider()
        if hasattr(storage, "init_tables"):
            storage.init_tables()
            return {"status": "ok", "message": "Tables initialized"}
        return {
            "status": "skipped",
            "message": "Storage provider does not support init_tables",
        }
    except Exception as e:
        return JSONResponse(
            status_code=500, content={"status": "error", "message": str(e)}
        )


# ============================================================================
# Include all routers
# ============================================================================

# Auth & Users (auth router already has /auth prefix, so it becomes /api/auth)
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")

# Grouped routers
app.include_router(stamps_router, prefix="/api")
app.include_router(translation_router, prefix="/api")
app.include_router(explore_router, prefix="/api")
app.include_router(chat_router, prefix="/api")
app.include_router(note_router, prefix="/api")
app.include_router(papers_router, prefix="/api")
app.include_router(upload_router, prefix="/api")

# PDF Analysis & Streaming
app.include_router(pdf_router, prefix="/api")

# Analysis Features
app.include_router(analysis_router, prefix="/api")
app.include_router(figures_router, prefix="/api")


# ============================================================================
# Main Page
# ============================================================================


@app.get("/")
async def root():
    """Root endpoint for API discovery."""
    return JSONResponse(
        content={
            "message": "PaperTerrace API Server",
            "version": "1.0.0",
            "docs": "/docs",
            "status": "active",
        }
    )


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    health_status = {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "cache": "in-memory",
    }
    return JSONResponse(health_status)


@app.get("/api/config")
async def get_config():
    """Returns configuration for the frontend."""
    return JSONResponse(content={"firebase_config": FIREBASE_CONFIG})
