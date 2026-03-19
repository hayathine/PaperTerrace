import json
import time
from datetime import datetime
from typing import Any

import redis

from common.config import get_redis_url, settings
from common.logger import get_service_logger

log = get_service_logger("Cache")

# 環境に応じた Redis URL を取得（prod/staging/local で接続先を切り替え）
REDIS_URL = get_redis_url()
REDIS_DB = int(settings.get("REDIS_DB", 0))
REDIS_PASSWORD = settings.get("REDIS_PASSWORD", None)

_RETRY_INTERVAL = 30.0  # 接続失敗後のリトライ間隔（秒）

_redis_client = None
_redis_enabled = True
_last_attempt_time: float = 0.0  # 0 = 未試行

_arq_pool = None


def get_redis_client():
    global _redis_client, _last_attempt_time
    if not _redis_enabled:
        return None

    now = time.monotonic()
    should_attempt = _redis_client is None and (now - _last_attempt_time) >= _RETRY_INTERVAL

    if should_attempt:
        _last_attempt_time = now
        try:
            client = redis.Redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            # test connection
            client.ping()
            _redis_client = client
            log.info("init", f"Connected to Redis at {REDIS_URL}")
        except Exception as e:
            log.warning(
                "init",
                f"Failed to connect to Redis ({REDIS_URL}): {e}. Will retry in {_RETRY_INTERVAL:.0f}s.",
            )
            _redis_client = None
    return _redis_client


async def get_arq_pool():
    """ARQ の async Redis pool を返す。未接続の場合は接続を試みる。接続不可なら None を返す。"""
    global _arq_pool
    if _arq_pool is not None:
        return _arq_pool

    try:
        from arq import create_pool
        from arq.connections import RedisSettings

        _arq_pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))
        log.info("arq_pool", f"ARQ pool connected to {REDIS_URL}")
    except Exception as e:
        log.warning("arq_pool", f"Failed to create ARQ pool ({REDIS_URL}): {e}")
        _arq_pool = None

    return _arq_pool


async def close_arq_pool() -> None:
    """ARQ pool を閉じる（lifespan shutdown 時に呼ぶ）。"""
    global _arq_pool
    if _arq_pool is not None:
        await _arq_pool.aclose()
        _arq_pool = None
        log.info("arq_pool", "ARQ pool closed")


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects."""

    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class RedisService:
    """Redis cache service with in-memory fallback."""

    # Shared memory cache across all instances for fallback
    _shared_cache: dict[str, Any] = {}

    def __init__(self):
        self.client = get_redis_client()
        self.memory_cache = RedisService._shared_cache
        if not hasattr(RedisService, "_initialized"):
            if self.client:
                log.info("init", f"RedisService initialized with host: {REDIS_URL}")
            else:
                log.warning(
                    "init",
                    "RedisService initialized with in-memory fallback (Redis unavailable)",
                )
            RedisService._initialized = True

    def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Set a value in cache."""
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value, cls=DateTimeEncoder)
        else:
            value_str = str(value)

        if self.client:
            try:
                if expire:
                    self.client.setex(key, expire, value_str)
                    log.info(
                        "set_ex", f"Value set in Redis: {key} (expires: {expire}s)"
                    )
                else:
                    self.client.set(key, value_str)
                    log.info("set", f"Value set in Redis: {key}")
                return True
            except Exception as e:
                log.warning(
                    "set", f"Redis error: {e}. Falling back to memory for key: {key}"
                )

        self.memory_cache[key] = value_str
        log.info("set_memory", f"Value set in Memory Cache: {key}")
        return True

    def get(self, key: str) -> Any | None:
        """Get a value from cache."""
        value_str = None
        if self.client:
            try:
                value_str = self.client.get(key)
                if value_str is not None:
                    log.info("get_hit", f"Cache HIT (Redis): {key}")
                else:
                    log.debug("get_miss", f"Cache MISS (Redis): {key}")
            except Exception as e:
                log.warning(
                    "get", f"Redis error for {key}: {e}. Falling back to memory."
                )

        if value_str is None:
            value_str = self.memory_cache.get(key)
            if value_str is not None:
                log.info("get_hit_memory", f"Cache HIT (Memory): {key}")
            else:
                log.debug("get_miss", f"Cache MISS (Overall): {key}")

        if value_str is None:
            return None

        try:
            return json.loads(str(value_str))
        except (json.JSONDecodeError, TypeError):
            return value_str

    def delete(self, key: str) -> int:
        """Delete a key from cache."""
        deleted_count = 0
        if self.client:
            try:
                deleted_count = self.client.delete(key)
                if deleted_count > 0:
                    log.info("delete_success", f"Key deleted from Redis: {key}")
            except Exception as e:
                log.warning(
                    "delete", f"Redis error for {key}: {e}. Falling back to memory."
                )

        # Always check memory cache just in case
        if key in self.memory_cache:
            del self.memory_cache[key]
            log.info("delete_memory", f"Key deleted from Memory Cache: {key}")
            deleted_count = 1

        return deleted_count

    def exists(self, key: str) -> bool:
        """Check if key exists in cache."""
        if self.client:
            try:
                return self.client.exists(key) > 0
            except Exception as e:
                log.warning("exists", f"Redis error: {e}. Falling back to memory.")

        return key in self.memory_cache

    def expire(self, key: str, time: int) -> bool:
        """Set a timeout on key."""
        if self.client:
            try:
                success = bool(self.client.expire(key, time))
                if success:
                    log.info("expire_success", f"TTL set for {key}: {time}s")
                return success
            except Exception as e:
                log.warning(
                    "expire", f"Redis error for {key}: {e}. Falling back to memory."
                )

        exists_in_mem = key in self.memory_cache
        if exists_in_mem:
            log.debug(
                "expire_memory",
                f"Expire called for memory key {key} (not supported, but key exists)",
            )
        return exists_in_mem

    def mget(self, *keys: str) -> list:
        """複数キーを1往復で取得する（Redis MGET）。失敗時は個別 get にフォールバック。"""
        if self.client:
            try:
                raw_values = self.client.mget(*keys)
                results = []
                for v in raw_values:
                    if v is None:
                        results.append(None)
                    else:
                        try:
                            results.append(json.loads(v))
                        except (json.JSONDecodeError, TypeError):
                            results.append(v)
                return results
            except Exception as e:
                log.warning("mget", f"Redis mget failed, falling back to individual gets: {e}")
        # メモリキャッシュ / fallback: 個別 get
        return [self.get(k) for k in keys]


def get_is_registered(user_id: str | None) -> bool:
    """ユーザー登録状態を Redis キャッシュ付きで確認する（TTL: 5分）。
    Redis / DB が失敗した場合は False を返す（フェイルセーフ）。
    """
    if not user_id:
        return False
    redis = RedisService()
    cache_key = f"user_registered:{user_id}"
    cached = redis.get(cache_key)
    if cached is not None:
        return bool(cached)
    # DB fallback
    try:
        from app.providers import get_storage_provider
        storage = get_storage_provider()
        is_reg = bool(storage.get_user(user_id))
        redis.set(cache_key, is_reg, expire=300)  # 5分キャッシュ
        return is_reg
    except Exception as e:
        log.warning("get_is_registered", f"Failed to check registration for {user_id}: {e}")
        return False
