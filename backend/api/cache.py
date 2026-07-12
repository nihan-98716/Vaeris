"""
backend/api/cache.py

Redis caching utility with graceful degradation if the Redis service is down.
"""

from typing import Optional

import redis

from backend.config import settings
from backend.logging import logger

_redis_client: Optional[redis.Redis] = None


def get_redis_client() -> Optional[redis.Redis]:
    """
    Lazily initializes and returns the Redis client.
    Returns None if Redis is unavailable.
    """
    global _redis_client
    if _redis_client is not None:
        return _redis_client

    try:
        client = redis.Redis(
            host=settings.redis.host,
            port=settings.redis.port,
            decode_responses=True,
            socket_connect_timeout=2.0,  # fail fast
        )
        # Ping to test connection
        client.ping()
        _redis_client = client
        logger.info(
            "Successfully connected to Redis cache instance",
            extra={"host": settings.redis.host, "port": settings.redis.port},
        )
        return _redis_client
    except Exception:
        logger.warning(
            "Redis cache is unavailable; running in degraded/non-cached mode",
            exc_info=False,
        )
        return None


def get_cached_value(key: str) -> Optional[str]:
    """
    Retrieves a value from the cache. Returns None on cache miss or cache error.
    """
    client = get_redis_client()
    if client is None:
        return None
    try:
        return client.get(key)
    except Exception:
        logger.error(f"Failed to read from Redis cache for key '{key}'", exc_info=True)
        return None


def set_cached_value(key: str, value: str, ttl_seconds: int) -> bool:
    """
    Saves a value in the cache with a specified TTL. Returns True on success, False on error.
    """
    client = get_redis_client()
    if client is None:
        return False
    try:
        client.set(key, value, ex=ttl_seconds)
        return True
    except Exception:
        logger.error(f"Failed to write to Redis cache for key '{key}'", exc_info=True)
        return False
