import json
import os
import time
from typing import Any, Optional

import redis

from src.logger import get_service_logger

log = get_service_logger("Redis")

# Singleton instance
_redis_client: Optional[redis.Redis] = None
_redis_error_logged = False
_last_connection_attempt = 0.0
RETRY_DELAY = 60  # Retry every 60 seconds if failed


def get_redis_client() -> Optional[redis.Redis]:
    """Get or create a Redis client instance (singleton). Returns None if connection fails."""
    global _redis_client, _redis_error_logged, _last_connection_attempt

    if _redis_client is not None:
        return _redis_client

    # Avoid frequent reconnection attempts if it previously failed
    current_time = time.time()
    if _redis_error_logged and (current_time - _last_connection_attempt) < RETRY_DELAY:
        return None

    host = os.getenv("REDIS_HOST", "localhost")
    port = int(os.getenv("REDIS_PORT", "6379"))
    db = int(os.getenv("REDIS_DB", "0"))

    _last_connection_attempt = current_time
    try:
        client = redis.Redis(host=host, port=port, db=db, decode_responses=True, socket_timeout=5)
        client.ping()
        _redis_client = client
        if _redis_error_logged:
            log.info("connect", "Redis recovered", host=host, port=port)
            _redis_error_logged = False
        else:
            log.info("connect", "Connected", host=host, port=port)
    except redis.ConnectionError as e:
        if not _redis_error_logged:
            log.warning("connect", "Connection failed, using memory fallback", error=str(e))
            _redis_error_logged = True
        _redis_client = None

    return _redis_client


class RedisService:
    """Wrapper for Redis operations with in-memory fallback."""

    def __init__(self):
        self.memory_cache: dict[str, Any] = {}

    def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Set a value in Redis (or memory) with optional expiration."""
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)

        client = get_redis_client()
        if client:
            try:
                return client.set(key, value_str, ex=expire)
            except Exception as e:
                log.error("set", "Operation failed", key=key, error=str(e))
                global _redis_client
                _redis_client = None
                return False
        else:
            self.memory_cache[key] = value_str
            return True

    def get(self, key: str) -> Any | None:
        """Get a value from Redis (or memory)."""
        value_str = None
        client = get_redis_client()
        if client:
            try:
                value_str = client.get(key)
            except Exception as e:
                log.error("get", "Operation failed", key=key, error=str(e))
                global _redis_client
                _redis_client = None
                return None
        else:
            value_str = self.memory_cache.get(key)

        if value_str is None:
            return None

        try:
            return json.loads(str(value_str))
        except (json.JSONDecodeError, TypeError):
            return value_str

    def delete(self, key: str) -> int:
        """Delete a key."""
        client = get_redis_client()
        if client:
            try:
                return int(client.delete(key))  # type: ignore
            except Exception as e:
                log.error("delete", "Operation failed", key=key, error=str(e))
                global _redis_client
                _redis_client = None
                return 0
        else:
            if key in self.memory_cache:
                del self.memory_cache[key]
                return 1
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        client = get_redis_client()
        if client:
            try:
                return bool(client.exists(key))
            except Exception as e:
                log.error("exists", "Operation failed", key=key, error=str(e))
                global _redis_client
                _redis_client = None
                return False
        else:
            return key in self.memory_cache
