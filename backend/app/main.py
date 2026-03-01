"""
PaperTerrace - AI-powered paper reading assistant
Main application entry point.
"""

import contextlib
import os
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
    contact_router,
    feedback_router,
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
        # If tables already exist, we might get a DuplicateTable error.
        # We log and continue so the app can still run.
        if "already exists" in str(e).lower():
            logger.warning(
                f"Database tables already exist, skipping initial migration: {e}"
            )
        else:
            logger.error(f"Failed to initialize database: {e}")
            # Re-raise for non-existence errors if necessary, or just continue
            # For now, let's allow the app to try to run.

    yield

    logger.info("Shutting down...")


# Create FastAPI app with lifespan
app = FastAPI(
    title="PaperTerrace",
    description="AI-powered paper reading assistant",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS configuration for Cloudflare Pages and Workers
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "https://paperterrace.pages.dev",
        "https://www.paperterrace.page",
        "https://paperterrace.page",
    ],
    allow_origin_regex=r"https://.*\.(paperterrace\.page|pages\.dev)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class TrustedProxyMiddleware(BaseHTTPMiddleware):
    """
    Middleware to extract user ID from X-User-ID header added by Cloudflare Workers API Gateway.
    Trusts the header since authentication is handled at the edge by Cloudflare Workers.
    """

    async def dispatch(self, request: Request, call_next):
        # Extract user ID from header added by API Gateway
        user_id = request.headers.get("x-user-id")
        if user_id:
            request.state.user_id = user_id
            logger.debug(f"Request authenticated for user: {user_id}")

        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log incoming requests and their responses.
    Includes success, failure, and execution duration.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        is_health_check = request.url.path == "/api/health"
        log_func = logger.debug if is_health_check else logger.info

        # Log request start
        log_func(
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
            log_func(
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


app.add_middleware(TrustedProxyMiddleware)
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
app.include_router(chat_router, prefix="/api")
app.include_router(note_router, prefix="/api")
app.include_router(papers_router, prefix="/api")
app.include_router(upload_router, prefix="/api")

# PDF Analysis & Streaming
app.include_router(pdf_router, prefix="/api")

# Analysis Features
app.include_router(analysis_router, prefix="/api")
app.include_router(figures_router, prefix="/api")
app.include_router(feedback_router, prefix="/api")
app.include_router(contact_router, prefix="/api")


# ============================================================================
# Static Files / Image Proxy (GCS-compatible)
# ============================================================================

_storage_type = os.getenv("STORAGE_TYPE", "local").lower()

if _storage_type == "gcs":
    # GCS mode: proxy image requests through the backend
    from fastapi import Path as FastAPIPath
    from fastapi.responses import Response as FastAPIResponse

    @app.get("/static/paper_images/{file_hash}/{filename}")
    async def serve_gcs_image(
        file_hash: str = FastAPIPath(...),
        filename: str = FastAPIPath(...),
    ):
        """Proxy GCS images to avoid CORS issues."""
        try:
            from app.providers.image_storage import _get_instance

            storage_inst = _get_instance()
            blob_name = f"paper_images/{file_hash}/{filename}"
            blob = storage_inst.bucket.blob(blob_name)

            if not blob.exists():
                return FastAPIResponse(status_code=404, content=b"Not Found")

            data = blob.download_as_bytes()
            content_type = "image/png" if filename.endswith(".png") else "image/jpeg"
            return FastAPIResponse(
                content=data,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except Exception as e:
            logger.error(f"Failed to serve GCS image: {e}")
            return FastAPIResponse(status_code=500, content=b"Internal Server Error")

else:
    # Local mode: mount static files directory
    from pathlib import Path as PathLib

    from starlette.staticfiles import StaticFiles

    _images_dir = PathLib(os.getenv("IMAGES_DIR", "src/static/paper_images"))
    _images_dir.mkdir(parents=True, exist_ok=True)
    app.mount(
        "/static/paper_images",
        StaticFiles(directory=str(_images_dir)),
        name="paper_images",
    )


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
    """Health check endpoint with dependencies verification."""
    from redis import Redis

    from app.providers import get_storage_provider

    status = "healthy"
    dependencies = {}

    # Check Database
    try:
        storage = get_storage_provider()
        # Just use the storage object to show it's initialized
        provider_name = storage.__class__.__name__
        dependencies["database"] = f"connected ({provider_name})"
    except Exception as e:
        status = "unhealthy"
        dependencies["database"] = f"error: {str(e)}"

    # Check Redis
    try:
        # redis_host = os.getenv("REDIS_HOST", "redis")
        # redis_port = int(os.getenv("REDIS_PORT", "6379"))
        redis_url = os.getenv("REDIS_URL", "redis://redis:6379")
        # socket_connect_timeout must be shorter than the liveness probe timeoutSeconds (10s)
        r = Redis.from_url(redis_url, socket_connect_timeout=1)
        r.ping()
        dependencies["redis"] = "connected"
    except Exception as e:
        status = "unhealthy"
        dependencies["redis"] = f"error: {str(e)}"

    health_status = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "dependencies": dependencies,
        "version": "1.0.0",
    }

    # Return 503 if unhealthy, unless we are in a testing environment
    is_testing = (
        os.getenv("ENV") == "testing" or os.getenv("PYTEST_CURRENT_TEST") is not None
    )
    status_code = 200 if (status == "healthy" or is_testing) else 503

    return JSONResponse(status_code=status_code, content=health_status)


@app.get("/api/config")
async def get_config():
    """Returns configuration for the frontend."""
    return JSONResponse(content={"firebase_config": FIREBASE_CONFIG})
