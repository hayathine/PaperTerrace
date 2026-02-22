"""
Provider package for AI and Storage abstraction.
Enables switching between local (Gemini/SQLite) and cloud (Vertex AI/Cloud SQL) providers.
"""

from redis_provider.provider import RedisService, get_redis_client

from .ai_provider import AIProviderInterface, GeminiProvider, get_ai_provider
from .image_storage import get_image_bytes, get_image_storage
from .storage_provider import SQLiteStorage, StorageInterface, get_storage_provider

__all__ = [
    "AIProviderInterface",
    "GeminiProvider",
    "get_ai_provider",
    "get_image_bytes",
    "get_image_storage",
    "StorageInterface",
    "SQLiteStorage",
    "get_storage_provider",
    "RedisService",
    "get_redis_client",
]
