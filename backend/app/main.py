"""
PaperTerrace - AI-powered paper reading assistant
Main application entry point.
"""

import contextlib
import traceback
from datetime import datetime

import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sentry_sdk.integrations.fastapi import FastApiIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
from starlette.middleware.cors import CORSMiddleware

from app.core.config import get_app_env, get_neon_auth_url, get_redis_url, is_production
from app.middleware import LoggingMiddleware, RateLimitMiddleware, TrustedProxyMiddleware, mw_log
from app.routers import (
    analysis_router,
    auth_router,
    chat_router,
    client_errors_router,
    contact_router,
    dspy_router,
    feedback_router,
    figures_router,
    note_router,
    papers_router,
    pdf_router,
    recommendation_router,
    stamps_router,
    translation_router,
    upload_router,
    users_router,
)
from common.config import settings
from common.logger import ServiceLogger

log = ServiceLogger("Main")

# ============================================================================
# Sentry / GlitchTip 初期化
# ============================================================================
_sentry_dsn = str(getattr(settings, "SENTRY_DSN", "") or "")
_sentry_enabled = bool(getattr(settings, "SENTRY_ENABLED", False))

if _sentry_enabled and _sentry_dsn:
    sentry_sdk.init(
        dsn=_sentry_dsn,
        integrations=[
            FastApiIntegration(),
            SqlalchemyIntegration(),
            LoggingIntegration(),  # ERROR 以上を自動キャプチャ
        ],
        traces_sample_rate=float(getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.1)),
        profiles_sample_rate=float(
            getattr(settings, "SENTRY_PROFILES_SAMPLE_RATE", 0.1)
        ),
        environment=get_app_env(),
        send_default_pii=False,
    )
    log.info("sentry", "Sentry initialized", dsn=_sentry_dsn[:40] + "...")
else:
    log.info("sentry", "Sentry disabled")


# Neon Auth Config for Frontend
NEON_AUTH_CONFIG = {
    "authUrl": get_neon_auth_url(),
}


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Lifespan event handler for FastAPI.
    Handles startup and shutdown events.
    """
    import asyncio

    from app.database import engine
    from app.providers import close_arq_pool, get_arq_pool

    async def _warmup_db_async() -> None:
        """DB接続ウォームアップ: コールドスタート後の初回リクエストレイテンシを削減。"""
        try:
            await asyncio.to_thread(_warmup_db, engine)
            log.info("lifespan", "DB warmup completed")
        except Exception as e:
            log.warning("lifespan", "DB warmup failed (non-fatal)", error=str(e))

    async def _warmup_arq_async() -> None:
        """ARQ pool 初期化（Redis 未接続環境では None になり、同期フォールバックが使われる）。"""
        try:
            await asyncio.wait_for(get_arq_pool(), timeout=5.0)
        except asyncio.TimeoutError:
            log.warning("lifespan", "ARQ pool initialization timed out (Redis may be unavailable)")
        except Exception as e:
            log.warning("lifespan", "ARQ pool initialization failed (non-fatal)", error=str(e))

    # DB warmup と ARQ pool 初期化を並列実行してコールドスタートを短縮
    await asyncio.gather(_warmup_db_async(), _warmup_arq_async())

    yield

    await close_arq_pool()


def _warmup_db(engine) -> None:
    """DBへの接続を1本確立してプールをウォームアップする。"""
    from sqlalchemy import text

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


# Create FastAPI app with lifespan
app = FastAPI(
    title="PaperTerrace",
    description="AI-powered paper reading assistant",
    version="1.0.0",
    lifespan=lifespan,
)


# CORS configuration for Cloudflare Pages and Workers
# 追加オリジンは CORS_EXTRA_ORIGINS 環境変数にカンマ区切りで指定可能
_default_origins = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "https://paperterrace.pages.dev",
    "https://www.paperterrace.page",
    "https://paperterrace.page",
]
_extra_origins_raw = settings.get("CORS_EXTRA_ORIGINS", "")
_extra_origins = [o.strip() for o in _extra_origins_raw.split(",") if o.strip()]
_allowed_origins = _default_origins + _extra_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_origin_regex=r"https://.*\.(paperterrace\.page|pages\.dev)",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ミドルウェアの実行順 (Starlette は LIFO): LoggingMW → TrustedProxyMW → RateLimitMW → Routes
app.add_middleware(RateLimitMiddleware)
app.add_middleware(TrustedProxyMiddleware)
app.add_middleware(LoggingMiddleware)


@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # Handle ExceptionGroup specifically for better logging
    error_msg_detail = str(exc)
    if hasattr(exc, "exceptions"):
        sub_errors = [str(se) for se in getattr(exc, "exceptions")]
        error_msg_detail = f"{type(exc).__name__}: {'; '.join(sub_errors)}"

    mw_log.error(
        "exception",
        "Global exception",
        method=request.method,
        path=request.url.path,
        error=error_msg_detail,
    )

    mw_log.error("exception", traceback.format_exc())

    # Hide detailed error message from end users in production
    error_msg = (
        error_msg_detail
        if not is_production()
        else "An unexpected error occurred. Please try again later."
    )

    return JSONResponse(
        status_code=500,
        content={"error": "Internal Server Error", "message": error_msg},
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
        app_env = settings.get("APP_ENV", "production")
        error_msg = str(e) if app_env == "local" else "Failed to initialize database"
        return JSONResponse(
            status_code=500, content={"status": "error", "message": error_msg}
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
app.include_router(dspy_router, prefix="/api")
app.include_router(contact_router, prefix="/api")
app.include_router(recommendation_router, prefix="/api")
app.include_router(client_errors_router, prefix="/api")


# ============================================================================
# Static Files / Image Proxy (GCS-compatible)
# ============================================================================

_storage_type = str(settings.get("STORAGE_TYPE", "local")).lower()

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
        import asyncio

        try:
            from app.providers.image_storage import _get_instance

            storage_inst = _get_instance()
            blob_name = f"paper_images/{file_hash}/{filename}"
            blob = storage_inst.bucket.blob(blob_name)

            exists = await asyncio.to_thread(blob.exists)
            if not exists:
                return FastAPIResponse(status_code=404, content=b"Not Found")

            data = await asyncio.to_thread(blob.download_as_bytes)
            ext = blob.name.rsplit(".", 1)[-1].lower()
            content_type = "image/webp" if ext == "webp" else "image/jpeg"
            return FastAPIResponse(
                content=data,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=86400",
                    "Access-Control-Allow-Origin": "*",
                },
            )
        except Exception as e:
            log.error("serve_gcs_image", "Failed to serve GCS image", error=str(e))
            return FastAPIResponse(status_code=500, content=b"Internal Server Error")


else:
    # Local mode: mount static files directory
    from pathlib import Path as PathLib

    from starlette.staticfiles import StaticFiles

    _images_dir = PathLib(settings.get("IMAGES_DIR", "src/static/paper_images"))
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

    # Check Redis (ローカル環境または localhost 設定では Redis 未接続でも healthy 扱い)
    from app.core.config import is_local
    try:
        _redis_url = get_redis_url()
        # socket_connect_timeout must be shorter than the liveness probe timeoutSeconds (10s)
        r = Redis.from_url(_redis_url, socket_connect_timeout=1)
        r.ping()
        dependencies["redis"] = "connected"
    except Exception as e:
        _redis_url = get_redis_url()
        is_redis_optional = is_local() or "localhost" in _redis_url
        if is_redis_optional:
            dependencies["redis"] = "unavailable (optional in this environment)"
        else:
            status = "unhealthy"
            dependencies["redis"] = f"error: {str(e)}"

    health_status = {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "dependencies": dependencies,
        "version": "1.0.0",
    }

    # Check Maintenance Mode
    maintenance_mode = str(settings.get("MAINTENANCE_MODE", "false")).lower() == "true"
    if maintenance_mode:
        return JSONResponse(
            status_code=503,
            content={
                "status": "maintenance",
                "message": "システムメンテナンス中です。しばらくお待ちください。",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            },
        )

    # Return 503 if unhealthy, unless we are in a testing environment
    is_testing = (
        settings.get("APP_ENV") == "testing" or settings.get("PYTEST_CURRENT_TEST") is not None
    )
    status_code = 200 if (status == "healthy" or is_testing) else 503

    return JSONResponse(status_code=status_code, content=health_status)


@app.get("/api/config")
async def get_config():
    """Returns configuration for the frontend."""
    return JSONResponse(
        content={
            "neon_auth": NEON_AUTH_CONFIG,
            "app_env": get_app_env(),
            "max_pdf_size_mb": int(settings.get("MAX_PDF_SIZE_MB", "50")),
        }
    )
