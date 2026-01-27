import json
import os
from typing import Any, Optional

import redis

from src.logger import logger

# Singleton instance
_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """Get or create a Redis client instance (singleton). Returns None if connection fails."""
    global _redis_client
    if _redis_client is None:
        host = os.getenv("REDIS_HOST", "localhost")
        port = int(os.getenv("REDIS_PORT", "6379"))
        db = int(os.getenv("REDIS_DB", "0"))

        try:
            client = redis.Redis(
                host=host, port=port, db=db, decode_responses=True, socket_timeout=5
            )
            # 接続テスト
            client.ping()
            _redis_client = client
            logger.info(f"Connected to Redis at {host}:{port}")
        except redis.ConnectionError as e:
            logger.warning(f"Failed to connect to Redis: {e}. Falling back to in-memory storage.")
            _redis_client = None

    return _redis_client


class RedisService:
    """Wrapper for Redis operations with in-memory fallback."""

    def __init__(self):
        self.client = get_redis_client()
        self.memory_cache: dict[str, Any] = {}

    def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Set a value in Redis (or memory) with optional expiration."""
        # JSON serialize for consistency
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)

        if self.client:
            try:
                return self.client.set(key, value_str, ex=expire)
            except Exception as e:
                logger.error(f"Redis SET failed for key {key}: {e}")
                return False
        else:
            # Memory fallback (ignoring expire)
            self.memory_cache[key] = value_str
            return True

    def get(self, key: str) -> Any | None:
        """Get a value from Redis (or memory)."""
        value_str = None
        if self.client:
            try:
                value_str = self.client.get(key)
            except Exception as e:
                logger.error(f"Redis GET failed for key {key}: {e}")
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
        if self.client:
            try:
                return int(self.client.delete(key))  # type: ignore
            except Exception as e:
                logger.error(f"Redis DELETE failed for key {key}: {e}")
                return 0
        else:
            if key in self.memory_cache:
                del self.memory_cache[key]
                return 1
            return 0

    def exists(self, key: str) -> bool:
        """Check if key exists."""
        if self.client:
            try:
                return bool(self.client.exists(key))
            except Exception as e:
                logger.error(f"Redis EXISTS failed for key {key}: {e}")
                return False
        else:
            return key in self.memory_cache
