import json
import uuid
from functools import lru_cache

from redis.asyncio import Redis
from redis.exceptions import WatchError

from app.config import get_settings
from app.core.logging_utils import log_cache_event, log_execution

SESSION_TTL_SECONDS = 60 * 60 * 48  # 48h — abandoned session cleanup
CHAPTER_BODY_TTL_SECONDS = 60 * 60 * 24  # 24h — invalidated explicitly on accept anyway
MAX_SAVE_RETRIES = 5  # WatchError retry ceiling before giving up as a real conflict

DEFAULT_STATE = {
    "running_summary": "",       # Trigger 1 output, empty until first compaction
    "raw_tail": [],              # list[str], most recent accepted paragraphs, verbatim
    "pending_turn": None,        # {"content": str, "instruction": str|None, "source": "ai"|"user_edit"}
    "sibling_attempts": [],      # list[pending_turn-shaped dict], bounded to 3
    "word_count_since_compaction": 0,
    "version": 0,                # optimistic concurrency guard
}


class SessionConflict(Exception):
    """Raised when save_session's optimistic check fails after exhausting
    retries — some other writer changed this chapter's session between this
    caller's read and its write. The caller should re-fetch via get_session
    and either recompute its change or surface a conflict to the user,
    never blind-retry with the same stale `state` dict."""

    def __init__(self, chapter_id: uuid.UUID):
        self.chapter_id = chapter_id
        super().__init__(f"Session for chapter {chapter_id} was modified concurrently")


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
    """Optimistic-locked write. `state["version"]` must be the version this
    caller originally read via get_session — NOT bumped by the caller.
    Retries automatically on a concurrent write (re-reads current Redis
    state, up to MAX_SAVE_RETRIES) since a WatchError only means "something
    else wrote in between," not that this caller's intended change is
    invalid. If the version has genuinely moved from what this caller read,
    raises SessionConflict — the caller must re-fetch and recompute."""
    key = _key(chapter_id)
    redis = _redis()
    expected_version = state["version"]

    for _ in range(MAX_SAVE_RETRIES):
        async with redis.pipeline(transaction=True) as pipe:
            try:
                await pipe.watch(key)
                raw = await pipe.get(key)
                current = json.loads(raw) if raw is not None else dict(DEFAULT_STATE)

                if current["version"] != expected_version:
                    await pipe.unwatch()
                    raise SessionConflict(chapter_id)

                state["version"] = expected_version + 1
                pipe.multi()
                pipe.set(key, json.dumps(state), ex=SESSION_TTL_SECONDS)
                await pipe.execute()
                return
            except WatchError:
                continue
    raise SessionConflict(chapter_id)


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
