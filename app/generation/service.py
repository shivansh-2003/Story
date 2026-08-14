import uuid
from collections.abc import AsyncIterator

from fastapi import BackgroundTasks
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import ChapterStatus
from app.chapters.service import get_prior_chapter_summaries, set_chapter_status
from app.core.llm_client import stream_model
from app.generation import assembler, session_store, summarizer
from app.generation.models import ChapterTurn

LENGTH_PRESETS = {"short": 50, "standard": 100, "long": 150}


async def prepare_continue(
    db: AsyncSession, chapter_id: uuid.UUID, story_id: uuid.UUID, instruction: str, length: str
) -> tuple[str, dict]:
    """DB-dependent prep for generate_continue — must run and finish before
    the router returns its StreamingResponse. FastAPI tears down `Depends(get_db)`
    as soon as the route handler returns, which for a streaming response happens
    immediately, before the generator body has run at all — so no DB access
    can happen inside the generator itself."""
    state = await session_store.get_session(chapter_id)
    prior_summaries = await get_prior_chapter_summaries(db, story_id, chapter_id)
    prompt = await assembler.build_continue_prompt(
        db, chapter_id, story_id, state, prior_summaries, instruction, LENGTH_PRESETS.get(length, 100)
    )
    return prompt, state


async def generate_continue(prompt: str, state: dict, chapter_id: uuid.UUID, instruction: str) -> AsyncIterator[str]:
    chunks: list[str] = []
    async for delta in stream_model(prompt, max_tokens=300):
        chunks.append(delta)
        yield delta

    if state["pending_turn"]:
        state["sibling_attempts"] = ([state["pending_turn"]] + state["sibling_attempts"])[:3]
    state["pending_turn"] = {"content": "".join(chunks), "instruction": instruction, "source": "ai"}
    await session_store.save_session(chapter_id, state)


async def prepare_edit(
    db: AsyncSession, chapter_id: uuid.UUID, story_id: uuid.UUID, instruction: str
) -> tuple[str, dict]:
    """Same DB-before-streaming constraint as prepare_continue. Also where
    "no pending turn to edit" (ValueError from the assembler) surfaces, so the
    router can still turn it into a normal 400 instead of a broken stream."""
    state = await session_store.get_session(chapter_id)
    prompt = await assembler.build_edit_prompt(db, chapter_id, story_id, state, instruction)
    return prompt, state


async def edit_pending(prompt: str, state: dict, chapter_id: uuid.UUID, instruction: str) -> AsyncIterator[str]:
    chunks: list[str] = []
    async for delta in stream_model(prompt, max_tokens=300):
        chunks.append(delta)
        yield delta

    state["sibling_attempts"] = ([state["pending_turn"]] + state["sibling_attempts"])[:3]
    state["pending_turn"] = {"content": "".join(chunks), "instruction": instruction, "source": "ai"}
    await session_store.save_session(chapter_id, state)


async def apply_manual_edit(chapter_id: uuid.UUID, new_content: str) -> dict:
    """User hand-edits the pending draft directly — no model call."""
    state = await session_store.get_session(chapter_id)
    state["pending_turn"] = {"content": new_content, "instruction": None, "source": "user_edit"}
    await session_store.save_session(chapter_id, state)
    return state["pending_turn"]


async def accept_pending(db: AsyncSession, chapter_id: uuid.UUID, background_tasks: BackgroundTasks) -> dict:
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

    state["raw_tail"].append(content)
    state["word_count_since_compaction"] += len(content.split())
    state["pending_turn"] = None
    state["sibling_attempts"] = []
    await session_store.save_session(chapter_id, state)

    background_tasks.add_task(summarizer.maybe_compact_session, chapter_id)
    return {"accepted": True, "sequence": next_sequence}


async def discard_pending(chapter_id: uuid.UUID) -> None:
    state = await session_store.get_session(chapter_id)
    state["pending_turn"] = None
    await session_store.save_session(chapter_id, state)


async def complete_chapter(db: AsyncSession, chapter_id: uuid.UUID, background_tasks: BackgroundTasks) -> dict:
    state = await session_store.get_session(chapter_id)
    if state["pending_turn"] is not None:
        # explicit rule: block, don't silently discard or include
        raise ValueError("Resolve the pending draft (accept or discard) before completing the chapter")

    await set_chapter_status(db, chapter_id, ChapterStatus.complete)
    background_tasks.add_task(summarizer.summarize_completed_chapter, chapter_id)
    return {"status": "complete", "summarizing": True}
