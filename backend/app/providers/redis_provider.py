import json
from typing import Any

from common.logger import get_service_logger

log = get_service_logger("Cache")

# Redis is disabled - using in-memory cache only
_redis_enabled = False


def get_redis_client() -> None:
    """Redis is disabled. Returns None to use in-memory fallback."""
    return None


class RedisService:
    """In-memory cache service (Redis disabled)."""

    # Shared memory cache across all instances
    _shared_cache: dict[str, Any] = {}

    def __init__(self):
        # Use shared cache to maintain state across service instances
        self.memory_cache = RedisService._shared_cache
        if not hasattr(RedisService, "_initialized"):
            log.info("init", "Using in-memory cache (Redis disabled)")
            RedisService._initialized = True

    def set(self, key: str, value: Any, expire: int | None = None) -> bool:
        """Set a value in memory cache. Note: expire parameter is ignored."""
        if isinstance(value, (dict, list)):
            value_str = json.dumps(value)
        else:
            value_str = str(value)

        self.memory_cache[key] = value_str
        return True

    def get(self, key: str) -> Any | None:
        """Get a value from memory cache."""
        value_str = self.memory_cache.get(key)

        if value_str is None:
            return None

        try:
            return json.loads(str(value_str))
        except (json.JSONDecodeError, TypeError):
            return value_str

    def delete(self, key: str) -> int:
        """Delete a key from memory cache."""
        if key in self.memory_cache:
            del self.memory_cache[key]
            return 1
        return 0

    def exists(self, key: str) -> bool:
        """Check if key exists in memory cache."""
        return key in self.memory_cache
