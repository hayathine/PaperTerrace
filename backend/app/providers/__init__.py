"""
Provider package for AI and Storage abstraction.
Enables switching between local (SQLite) and cloud (Vertex AI/Cloud SQL) providers.
"""

from redis_provider.provider import RedisService, close_arq_pool, get_arq_pool, get_redis_client

from .ai_provider import AIProviderInterface, GeminiProvider, VertexAIProvider, get_ai_provider
from .image_storage import get_image_bytes, get_image_storage
from .orm_storage import ORMStorageAdapter
from .storage_provider import SQLiteStorage, StorageInterface, get_storage_provider

__all__ = [
    "AIProviderInterface",
    "VertexAIProvider",
    "GeminiProvider",
    "get_ai_provider",
    "get_image_bytes",
    "get_image_storage",
    "StorageInterface",
    "SQLiteStorage",
    "get_storage_provider",
    "ORMStorageAdapter",
    "RedisService",
    "get_redis_client",
    "get_arq_pool",
    "close_arq_pool",
]
