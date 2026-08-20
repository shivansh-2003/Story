import asyncio
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import Chapter, ChapterStatus
from app.chapters.service import set_chapter_status
from app.core.llm_client import stream_model
from app.core.logging_utils import log_execution
from app.database import async_session
from app.generation import assembler, embedder, session_store, summarizer
from app.generation.models import ChapterTurn

logger = logging.getLogger("story_assistant.generation")

LENGTH_PRESETS = {"short": 50, "standard": 100, "long": 150}
# ~2.2x the word target — headroom, since models don't hit word counts exactly,
# while still giving "short" a real cost/latency ceiling below "long".
LENGTH_TOKEN_CEILINGS = {"short": 120, "standard": 220, "long": 320}


@log_execution(label="PREPARE_PHASE")
async def prepare_continue(
    db: AsyncSession, chapter: Chapter, story_id: uuid.UUID, instruction: str, length: str
) -> tuple[str, str, dict]:
    """DB-dependent prep for generate_continue — must run and finish before
    the router returns its StreamingResponse. FastAPI tears down `Depends(get_db)`
    as soon as the route handler returns, which for a streaming response happens
    immediately, before the generator body has run at all — so no DB access
    can happen inside the generator itself.

    Takes the already-fetched Chapter (from the router's ownership check)
    instead of a bare id, so the lock check and status write don't re-query
    a row the caller already has.

    Returns (system, user, state)."""
    if chapter.status == ChapterStatus.locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Chapter is locked — unlock it before generating or editing.")
    chapter_id = chapter.id
    state = await session_store.get_session(chapter_id)
    # the in_progress status write doesn't gate prompt assembly — they touch
    # unrelated data, so run them concurrently instead of paying the status
    # UPDATE's round-trip before assembly even starts.
    _, (system, user) = await asyncio.gather(
        set_chapter_status(db, chapter_id, ChapterStatus.in_progress, chapter=chapter),
        assembler.build_continue_prompt(chapter_id, story_id, state, instruction, LENGTH_PRESETS.get(length, 100)),
    )
    return system, user, state


@log_execution(label="GENERATE")
async def generate_continue(
    system: str, user: str, state: dict, chapter_id: uuid.UUID, instruction: str, length: str
) -> AsyncIterator[str]:
    max_tokens = LENGTH_TOKEN_CEILINGS.get(length, LENGTH_TOKEN_CEILINGS["standard"])
    chunks: list[str] = []
    async for delta in stream_model(user, max_tokens=max_tokens, system=system):
        chunks.append(delta)
        yield delta

    if state["pending_turn"]:
        state["sibling_attempts"] = ([state["pending_turn"]] + state["sibling_attempts"])[:3]
    state["pending_turn"] = {"content": "".join(chunks), "instruction": instruction, "source": "ai"}
    await session_store.save_session(chapter_id, state)
    await _mark_in_review(chapter_id)


@log_execution(label="PREPARE_PHASE")
async def prepare_edit(
    db: AsyncSession, chapter: Chapter, story_id: uuid.UUID, instruction: str
) -> tuple[str, str, dict]:
    """Same DB-before-streaming constraint as prepare_continue. Also where
    "no pending turn to edit" (ValueError from the assembler) surfaces, so the
    router can still turn it into a normal 400 instead of a broken stream.

    Returns (system, user, state)."""
    if chapter.status == ChapterStatus.locked:
        raise HTTPException(status.HTTP_409_CONFLICT, "Chapter is locked — unlock it before generating or editing.")
    chapter_id = chapter.id
    state = await session_store.get_session(chapter_id)
    _, (system, user) = await asyncio.gather(
        set_chapter_status(db, chapter_id, ChapterStatus.in_progress, chapter=chapter),
        assembler.build_edit_prompt(chapter_id, story_id, state, instruction),
    )
    return system, user, state


@log_execution(label="EDIT")
async def edit_pending(
    system: str, user: str, state: dict, chapter_id: uuid.UUID, instruction: str
) -> AsyncIterator[str]:
    # edits have no length preset of their own — "standard" is a reasonable
    # ceiling since an edit is a revision, not meant to grow the text much.
    chunks: list[str] = []
    async for delta in stream_model(user, max_tokens=LENGTH_TOKEN_CEILINGS["standard"], system=system):
        chunks.append(delta)
        yield delta

    state["sibling_attempts"] = ([state["pending_turn"]] + state["sibling_attempts"])[:3]
    state["pending_turn"] = {"content": "".join(chunks), "instruction": instruction, "source": "ai"}
    await session_store.save_session(chapter_id, state)
    await _mark_in_review(chapter_id)


@log_execution
async def _mark_in_review(chapter_id: uuid.UUID) -> None:
    # runs after the streaming response has already sent its content, so the
    # request's own db session (torn down when the router returned) can't be
    # reused — same reason prepare_*/generator are split in the first place.
    # Best-effort: the draft is already safely in Redis regardless of whether
    # this bookkeeping write lands, and a stuck status self-heals on the next
    # generate/accept/discard (see the in_review docstring note below).
    try:
        async with async_session() as db:
            await set_chapter_status(db, chapter_id, ChapterStatus.in_review)
    except Exception:
        logger.warning("failed to mark chapter %s as in_review", chapter_id, exc_info=True)


@log_execution
async def apply_manual_edit(chapter_id: uuid.UUID, new_content: str) -> dict:
    """User hand-edits the pending draft directly — no model call."""
    state = await session_store.get_session(chapter_id)
    state["pending_turn"] = {"content": new_content, "instruction": None, "source": "user_edit"}
    await session_store.save_session(chapter_id, state)
    return state["pending_turn"]


@log_execution
async def accept_pending(db: AsyncSession, chapter: Chapter, background_tasks: BackgroundTasks) -> dict:
    chapter_id = chapter.id
    state = await session_store.get_session(chapter_id)
    if state["pending_turn"] is None:
        raise ValueError("Nothing to accept")

    content = state["pending_turn"]["content"]
    instruction = state["pending_turn"]["instruction"]

    next_sequence = await db.scalar(
        select(func.coalesce(func.max(ChapterTurn.sequence), -1) + 1).where(ChapterTurn.chapter_id == chapter_id)
    )
    turn = ChapterTurn(chapter_id=chapter_id, sequence=next_sequence, content=content, instruction=instruction)
    db.add(turn)
    await db.commit()
    await session_store.invalidate_chapter_body(chapter_id)

    state["raw_tail"].append(content)
    state["word_count_since_compaction"] += len(content.split())
    state["pending_turn"] = None
    state["sibling_attempts"] = []
    await session_store.save_session(chapter_id, state)
    await set_chapter_status(db, chapter_id, ChapterStatus.in_progress, chapter=chapter)

    background_tasks.add_task(summarizer.maybe_compact_session, chapter_id)
    background_tasks.add_task(embedder.embed_turn, turn.id)
    return {"accepted": True, "sequence": next_sequence}


@log_execution
async def discard_pending(db: AsyncSession, chapter: Chapter) -> None:
    chapter_id = chapter.id
    state = await session_store.get_session(chapter_id)
    state["pending_turn"] = None
    await session_store.save_session(chapter_id, state)

    has_turns = await db.scalar(select(ChapterTurn.id).where(ChapterTurn.chapter_id == chapter_id).limit(1))
    new_status = ChapterStatus.in_progress if has_turns else ChapterStatus.draft
    await set_chapter_status(db, chapter_id, new_status, chapter=chapter)


@log_execution
async def complete_chapter(db: AsyncSession, chapter: Chapter, background_tasks: BackgroundTasks) -> dict:
    chapter_id = chapter.id
    state = await session_store.get_session(chapter_id)
    if state["pending_turn"] is not None:
        # explicit rule: block, don't silently discard or include
        raise ValueError("Resolve the pending draft (accept or discard) before completing the chapter")

    await set_chapter_status(db, chapter_id, ChapterStatus.complete, chapter=chapter)
    background_tasks.add_task(summarizer.summarize_completed_chapter, chapter_id)
    return {"status": "complete", "summarizing": True}
