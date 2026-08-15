import json
import uuid
from functools import lru_cache

from redis.asyncio import Redis

from app.config import get_settings
from app.core.logging_utils import log_cache_event, log_execution

SESSION_TTL_SECONDS = 60 * 60 * 48  # 48h — abandoned session cleanup
CHAPTER_BODY_TTL_SECONDS = 60 * 60 * 24  # 24h — invalidated explicitly on accept anyway

DEFAULT_STATE = {
    "running_summary": "",       # Trigger 1 output, empty until first compaction
    "raw_tail": [],              # list[str], most recent accepted paragraphs, verbatim
    "pending_turn": None,        # {"content": str, "instruction": str|None, "source": "ai"|"user_edit"}
    "sibling_attempts": [],      # list[pending_turn-shaped dict], bounded to 3
    "word_count_since_compaction": 0,
    "version": 0,                # optimistic concurrency guard
}


@lru_cache
def _redis() -> Redis:
    return Redis.from_url(get_settings().redis_url, decode_responses=True)


def _key(chapter_id: uuid.UUID) -> str:
    return f"chapter_session:{chapter_id}"


def _body_key(chapter_id: uuid.UUID) -> str:
    return f"chapter_body:{chapter_id}"


# _redis() and _key() deliberately NOT decorated — one-line helpers (a
# cached client getter, an f-string), no real work to time.


@log_execution
async def get_session(chapter_id: uuid.UUID) -> dict:
    key = _key(chapter_id)
    raw = await _redis().get(key)
    # Not a cache in the strict sense (it's session state, the only copy of
    # an in-progress draft) — logged the same way anyway so the
    # hit/miss pattern is consistent with wherever real caching lands later.
    log_cache_event(key, hit=raw is not None, source=f"{__name__}.get_session")
    if raw is None:
        return dict(DEFAULT_STATE)
    return json.loads(raw)


@log_execution
async def save_session(chapter_id: uuid.UUID, state: dict) -> None:
    state["version"] += 1
    await _redis().set(_key(chapter_id), json.dumps(state), ex=SESSION_TTL_SECONDS)


@log_execution
async def clear_session(chapter_id: uuid.UUID) -> None:
    await _redis().delete(_key(chapter_id))


@log_execution
async def get_cached_chapter_body(chapter_id: uuid.UUID) -> str | None:
    key = _body_key(chapter_id)
    cached = await _redis().get(key)
    log_cache_event(key, hit=cached is not None, source=f"{__name__}.get_cached_chapter_body")
    return cached


@log_execution
async def set_cached_chapter_body(chapter_id: uuid.UUID, body: str) -> None:
    await _redis().set(_body_key(chapter_id), body, ex=CHAPTER_BODY_TTL_SECONDS)


@log_execution
async def invalidate_chapter_body(chapter_id: uuid.UUID) -> None:
    await _redis().delete(_body_key(chapter_id))
