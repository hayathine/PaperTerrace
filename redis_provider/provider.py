import json
import os
from typing import Any

import redis

from common.logger import get_service_logger

log = get_service_logger("Cache")

# Load Redis host/port from env
# REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
# REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
REDIS_DB = int(os.getenv("REDIS_DB", 0))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", None)

_redis_client = None
_redis_enabled = True
_redis_attempted = False


def get_redis_client():
    global _redis_client, _redis_attempted
    if not _redis_enabled:
        return None

    if _redis_client is None and not _redis_attempted:
        _redis_attempted = True
        try:
            _redis_client = redis.Redis.from_url(
                REDIS_URL,
                decode_responses=True,
                socket_timeout=5.0,
                socket_connect_timeout=5.0,
            )
            # test connection
            _redis_client.ping()
            log.info("init", f"Connected to Redis at {REDIS_URL}")
        except Exception as e:
            log.warning(
                "init",
                f"Failed to connect to Redis ({REDIS_URL}): {e}. Using in-memory fallback.",
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
            value_str = json.dumps(value)
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
