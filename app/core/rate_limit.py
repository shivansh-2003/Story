import time
import uuid
from functools import lru_cache

from fastapi import HTTPException, status
from redis.asyncio import Redis

from app.config import get_settings
from app.core.logging_utils import log_execution

BUCKET_SIZE = 10          # max burst — lets a writer regenerate several times quickly
REFILL_SECONDS = 6        # 1 token refills every 6s => ~10 requests/minute sustained
BUCKET_KEY_TTL = 3600     # expire idle buckets — no need to persist a dormant user's state


@lru_cache
def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def _bucket_key(user_id: uuid.UUID, scope: str) -> str:
    return f"rate_limit:{scope}:{user_id}"


@log_execution
async def check_and_consume(user_id: uuid.UUID, scope: str = "generate") -> tuple[bool, float]:
    """Returns (allowed, retry_after_seconds). Refills lazily on each call
    based on elapsed time since last_refill_at — no scheduled job needed."""
    key = _bucket_key(user_id, scope)
    redis = _redis()
    now = time.time()

    raw = await redis.hgetall(key)
    tokens = float(raw.get("tokens", BUCKET_SIZE))
    last_refill_at = float(raw.get("last_refill_at", now))

    elapsed = max(0.0, now - last_refill_at)
    tokens = min(BUCKET_SIZE, tokens + elapsed / REFILL_SECONDS)

    if tokens < 1:
        retry_after = REFILL_SECONDS * (1 - tokens)
        return False, retry_after

    await redis.hset(key, mapping={"tokens": tokens - 1, "last_refill_at": now})
    await redis.expire(key, BUCKET_KEY_TTL)
    return True, 0.0


async def enforce_generation_rate_limit(user_id: uuid.UUID) -> None:
    """FastAPI dependency body — raises 429 with Retry-After if the bucket
    is empty, otherwise consumes a token and returns silently."""
    allowed, retry_after = await check_and_consume(user_id, scope="generate")
    if not allowed:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Generation rate limit exceeded — please slow down.",
            headers={"Retry-After": str(int(retry_after) + 1)},
        )


def _demo() -> None:
    import asyncio

    async def run():
        user_id = uuid.uuid4()
        for i in range(BUCKET_SIZE):
            allowed, _ = await check_and_consume(user_id)
            assert allowed, f"request {i} should have been allowed within burst"
        allowed, retry_after = await check_and_consume(user_id)
        assert not allowed and retry_after > 0
        print("rate_limit self-check passed")

    asyncio.run(run())


if __name__ == "__main__":
    _demo()
