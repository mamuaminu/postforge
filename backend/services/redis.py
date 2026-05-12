# © 2025 Mamu — All Rights Reserved
"""Redis client for caching and rate limiting."""
import redis.asyncio as redis
import os

_redis: redis.Redis = None


async def init_redis():
    global _redis
    try:
        _redis = redis.from_url(
            os.environ.get("REDIS_URL", "redis://localhost:6379/0"),
            encoding="utf-8",
            decode_responses=True,
        )
        await _redis.ping()
    except Exception as e:
        import logging
        logging.getLogger("postforge.redis").warning(f"Redis unavailable: {e}")


async def get_redis() -> redis.Redis:
    return _redis
