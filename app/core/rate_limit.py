import uuid

from fastapi import HTTPException, status
from app.core.logging_utils import log_execution
from app.core.redis_client import redis_client

BUCKET_SIZE = 10          # max burst — lets a writer regenerate several times quickly
REFILL_SECONDS = 6        # 1 token refills every 6s => ~10 requests/minute sustained
BUCKET_KEY_TTL = 3600     # expire idle buckets — no need to persist a dormant user's state


# Redis time avoids clock skew between API processes. Lua makes consumption
# atomic across all requests, including requests served by different workers.
TOKEN_BUCKET_SCRIPT = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + tonumber(clock[2]) / 1000000
local capacity = tonumber(ARGV[1])
local refill = tonumber(ARGV[2])
local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens')) or capacity
local previous = tonumber(redis.call('HGET', KEYS[1], 'last_refill_at')) or now
tokens = math.min(capacity, tokens + math.max(0, now - previous) / refill)
local allowed = 0
local retry = 0
if tokens >= 1 then
    tokens = tokens - 1
    allowed = 1
else
    retry = math.ceil(refill * (1 - tokens) * 1000)
end
redis.call('HSET', KEYS[1], 'tokens', tostring(tokens), 'last_refill_at', tostring(now))
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
return {allowed, retry}
"""


def _bucket_key(user_id: uuid.UUID, scope: str) -> str:
    return f"rate_limit:{scope}:{user_id}"


@log_execution
async def check_and_consume(user_id: uuid.UUID, scope: str = "generate") -> tuple[bool, float]:
    """Returns (allowed, retry_after_seconds). Refills lazily on each call
    based on elapsed time since last_refill_at — no scheduled job needed."""
    key = _bucket_key(user_id, scope)
    allowed, retry_ms = await redis_client().eval(
        TOKEN_BUCKET_SCRIPT, 1, key, BUCKET_SIZE, REFILL_SECONDS, BUCKET_KEY_TTL
    )
    return bool(allowed), retry_ms / 1000


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
