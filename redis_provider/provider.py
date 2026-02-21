import json
import os
from typing import Any

import redis
from common.logger import get_service_logger

log = get_service_logger("Cache")

# Load Redis host/port from env
REDIS_HOST = os.getenv("REDIS_SERVER", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

_redis_client = None
_redis_enabled = True


def get_redis_client():
    global _redis_client
    if not _redis_enabled:
        return None

    if _redis_client is None:
        try:
            _redis_client = redis.Redis(
                host=REDIS_HOST,
                port=REDIS_PORT,
                db=REDIS_DB,
                password=REDIS_PASSWORD,
                decode_responses=True,
            )
            # test connection
            _redis_client.ping()
            log.info(
                "init", f"Connected to Redis at {REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
            )
        except Exception as e:
            log.warning(
                "init",
                f"Failed to connect to Redis ({REDIS_HOST}:{REDIS_PORT}): {e}. Using in-memory fallback.",
            )
            _redis_client = None
    return _redis_client


class RedisService:
    """Redis cache service with in-memory fallback."""

    # Shared memory cache across all instances for fallback
    _shared_cache: dict[str, Any] = {}

    def __init__(self):
        self.client = get_redis_client()
        self.memory_cache = RedisService._shared_cache
        if not hasattr(RedisService, "_initialized"):
            if self.client:
                log.info("init", f"RedisService initialized with host: {REDIS_HOST}")
            else:
                log.info("init", "RedisService initialized with in-memory fallback")
            RedisService._initialized = True

    def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Set a value in cache."""
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)

        if self.client:
            try:
                if expire:
                    self.client.setex(key, expire, value_str)
                else:
                    self.client.set(key, value_str)
                return True
            except Exception as e:
                log.warning("set", f"Redis error: {e}. Falling back to memory.")

        self.memory_cache[key] = value_str
        return True

    def get(self, key: str) -> Any | None:
        """Get a value from cache."""
        value_str = None
        if self.client:
            try:
                value_str = self.client.get(key)
            except Exception as e:
                log.warning("get", f"Redis error: {e}. Falling back to memory.")

        if value_str is None:
            value_str = self.memory_cache.get(key)

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
            except Exception as e:
                log.warning("delete", f"Redis error: {e}. Falling back to memory.")

        # Always check memory cache just in case
        if key in self.memory_cache:
            del self.memory_cache[key]
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
