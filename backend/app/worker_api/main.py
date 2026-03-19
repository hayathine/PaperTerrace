"""
Worker API

k8s 内部で動作する軽量 FastAPI サービス。
Redis・ARQ に直接アクセスしてジョブの投入・ステータス管理を担う。
Cloud Run はこの API を HTTP で呼ぶだけでよく、Redis に直接接続しない。
"""

from contextlib import asynccontextmanager

import redis as sync_redis_lib
from arq import create_pool
from arq.connections import RedisSettings
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_redis_url
from app.worker_api.routers import jobs
from common.logger import ServiceLogger, configure_logging

configure_logging()
log = ServiceLogger("WorkerAPI")

_redis_client: sync_redis_lib.Redis | None = None
_arq_pool = None


def get_redis() -> sync_redis_lib.Redis | None:
    """同期 Redis クライアントを返す。"""
    return _redis_client


def get_arq():
    """ARQ async pool を返す。"""
    return _arq_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _redis_client, _arq_pool

    redis_url = get_redis_url()
    log.info("startup", "Worker API starting", redis_url=redis_url)

    _redis_client = sync_redis_lib.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_timeout=5.0,
        socket_connect_timeout=5.0,
    )
    _arq_pool = await create_pool(RedisSettings.from_dsn(redis_url))
    log.info("startup", "Redis + ARQ pool connected")

    yield

    if _arq_pool:
        await _arq_pool.aclose()
    log.info("shutdown", "Worker API stopped")


app = FastAPI(
    title="PaperTerrace Worker API",
    description="ジョブ管理 API（k8s 内部専用）",
    lifespan=lifespan,
)

# フロントエンドからの直接 SSE 接続を許可（job_id が認証トークン代わり）
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://paperterrace.page", "https://www.paperterrace.page"],
    allow_origin_regex=r"https://.*\.paperterrace\.page",
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(jobs.router)


@app.get("/health")
async def health():
    """ヘルスチェックエンドポイント。"""
    redis_ok = False
    try:
        if _redis_client:
            _redis_client.ping()
            redis_ok = True
    except Exception:
        pass

    return {
        "status": "healthy" if redis_ok else "degraded",
        "redis": "connected" if redis_ok else "unavailable",
    }
