import time
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.config import get_redis_url, is_production
from common.config import settings
from common.logger import ServiceLogger

mw_log = ServiceLogger("Middleware")


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    IPアドレス / ユーザーIDベースの固定ウィンドウレートリミット。
    Redis が利用不可の場合は制限をスキップし、可用性を優先する。
    - 登録ユーザー: RATE_LIMIT_REGISTERED req/分 (デフォルト 120)
    - ゲスト:       RATE_LIMIT_GUEST req/分 (デフォルト 30)
    """

    WINDOW_SECONDS = 60
    REGISTERED_LIMIT = int(settings.get("RATE_LIMIT_REGISTERED", "120"))
    GUEST_LIMIT = int(settings.get("RATE_LIMIT_GUEST", "30"))
    # レートリミット対象外のパス
    _SKIP_PATHS = frozenset(["/api/health", "/health", "/"])
    # レートリミット対象外のプレフィックス（ポーリング系エンドポイント）
    _SKIP_PREFIXES = ("/api/layout-jobs/",)

    def __init__(self, app):
        super().__init__(app)
        try:
            from redis import Redis

            client = Redis.from_url(
                get_redis_url(), socket_connect_timeout=1, decode_responses=True
            )
            client.ping()
            self._redis = client
        except Exception:
            self._redis = None

    async def dispatch(self, request: Request, call_next):
        if request.url.path in self._SKIP_PATHS:
            return await call_next(request)

        if any(request.url.path.startswith(p) for p in self._SKIP_PREFIXES):
            return await call_next(request)

        if not self._redis:
            return await call_next(request)

        # TrustedProxyMiddleware が先に設定した user_id を使用
        user_id = getattr(request.state, "user_id", None)
        identifier = user_id or (request.client.host if request.client else "unknown")
        limit = self.REGISTERED_LIMIT if user_id else self.GUEST_LIMIT
        key = f"rate:{identifier}"

        try:
            count = self._redis.incr(key)
            if count == 1:
                self._redis.expire(key, self.WINDOW_SECONDS)

            if count > limit:
                retry_after = self._redis.ttl(key)
                return JSONResponse(
                    status_code=429,
                    content={
                        "error": "Too Many Requests",
                        "message": "リクエスト制限に達しました。しばらく待ってから再試行してください。",
                    },
                    headers={"Retry-After": str(max(retry_after, 1))},
                )
        except Exception as e:
            mw_log.warning(
                "rate_limit", "Redis error, skipping rate limit", error=str(e)
            )

        return await call_next(request)


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
            mw_log.debug("auth", "Request authenticated", user_id=user_id)

        return await call_next(request)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware to log incoming requests and their responses.
    Includes success, failure, and execution duration.
    """

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        if request.url.path in ["/api/health", "/health"]:
            return await call_next(request)

        # Log request start
        mw_log.info(
            "request",
            "started",
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params),
            client_host=request.client.host if request.client else "unknown",
        )

        try:
            response = await call_next(request)
            duration = time.time() - start_time

            # Log request completion
            mw_log.info(
                "request",
                "completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=round(duration * 1000, 2),
            )
            return response
        except BaseException as e:
            if isinstance(e, (KeyboardInterrupt, SystemExit, GeneratorExit)):
                raise

            duration = time.time() - start_time

            # Handle ExceptionGroup/BaseExceptionGroup specifically for better logging
            error_msg_detail = str(e)
            if hasattr(e, "exceptions"):
                sub_errors = [str(se) for se in getattr(e, "exceptions")]
                error_msg_detail = f"{type(e).__name__}: {'; '.join(sub_errors)}"

            mw_log.error(
                "request",
                "failed",
                method=request.method,
                path=request.url.path,
                error=error_msg_detail,
                error_type=type(e).__name__,
                duration_ms=round(duration * 1000, 2),
            )
            mw_log.error("request", traceback.format_exc())

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


class StorageMiddleware(BaseHTTPMiddleware):
    """
    Middleware to provide a request-scoped database storage session.
    Prevents connection leaks by ensuring each request gets a fresh session,
    which is closed automatically after the response is sent.
    """

    async def dispatch(self, request: Request, call_next):
        from app.database import SessionLocal
        from app.providers.orm_storage import ORMStorageAdapter
        from app.providers.storage_provider import storage_context

        # Skip storage for health checks to minimize DB load
        if request.url.path in ["/api/health", "/health", "/"]:
            return await call_next(request)

        db = SessionLocal()
        storage = ORMStorageAdapter(db)
        token = storage_context.set(storage)

        try:
            response = await call_next(request)
            return response
        finally:
            storage.close()  # Also closes the underlying session
            storage_context.reset(token)
