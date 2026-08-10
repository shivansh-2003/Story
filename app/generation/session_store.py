import json
import uuid
from functools import lru_cache

from redis.asyncio import Redis

from app.config import get_settings

SESSION_TTL_SECONDS = 60 * 60 * 48  # 48h — abandoned session cleanup

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


async def get_session(chapter_id: uuid.UUID) -> dict:
    raw = await _redis().get(_key(chapter_id))
    if raw is None:
        return dict(DEFAULT_STATE)
    return json.loads(raw)


async def save_session(chapter_id: uuid.UUID, state: dict) -> None:
    state["version"] += 1
    await _redis().set(_key(chapter_id), json.dumps(state), ex=SESSION_TTL_SECONDS)


async def clear_session(chapter_id: uuid.UUID) -> None:
    await _redis().delete(_key(chapter_id))
