"""One Redis pool shared by draft sessions and rate limiting."""

from functools import lru_cache

from redis.asyncio import Redis

from app.config import get_settings


@lru_cache
def redis_client() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


async def close_redis_client() -> None:
    if redis_client.cache_info().currsize:
        client = redis_client()
        redis_client.cache_clear()
        await client.aclose()
