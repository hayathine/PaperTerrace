import time
import traceback

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from common.logger import logger


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
