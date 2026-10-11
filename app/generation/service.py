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
from app.generation import assembler, session_store
from app.generation.models import ChapterTurn
from app.jobs.models import BackgroundJob
from app.manuscript import service as manuscript
from app.manuscript.schemas import TurnRead
from app.planning import service as planning

logger = logging.getLogger("story_assistant.generation")

LENGTH_PRESETS = {"short": 50, "standard": 100, "long": 150}
# ~2.2x the word target — headroom, since models don't hit word counts exactly,
# while still giving "short" a real cost/latency ceiling below "long".
LENGTH_TOKEN_CEILINGS = {"short": 120, "standard": 220, "long": 320}


@log_execution(label="PREPARE_PHASE")
async def prepare_continue(
    db: AsyncSession, chapter: Chapter, story_id: uuid.UUID, instruction: str, length: str,
    scene_id: uuid.UUID | None = None,
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
    state["manuscript_revision"] = chapter.manuscript_revision
    context = await planning.generation_context(db, chapter, scene_id)
    state["generation_scene_id"] = context["scene_id"]
    state["planning_revision"] = context["planning_revision"]
    # the in_progress status write doesn't gate prompt assembly — they touch
    # unrelated data, so run them concurrently instead of paying the status
    # UPDATE's round-trip before assembly even starts.
    _, (system, user) = await asyncio.gather(
        set_chapter_status(db, chapter_id, ChapterStatus.in_progress, chapter=chapter),
        assembler.build_continue_prompt(chapter_id, story_id, state, instruction, LENGTH_PRESETS.get(length, 100), context),
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
    state["pending_turn"] = {"content": "".join(chunks), "instruction": instruction, "source": "ai", "draft_id": str(uuid.uuid4()), "base_revision": state["manuscript_revision"], "scene_id": state.get("generation_scene_id"), "base_planning_revision": state.get("planning_revision", 0)}
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
    state["manuscript_revision"] = chapter.manuscript_revision
    if state["pending_turn"] is None:
        raise ValueError("No pending turn to edit")
    scene_id = state["pending_turn"].get("scene_id")
    context = await planning.generation_context(db, chapter, uuid.UUID(scene_id) if scene_id else None)
    state["generation_scene_id"] = context["scene_id"]
    state["planning_revision"] = context["planning_revision"]
    _, (system, user) = await asyncio.gather(
        set_chapter_status(db, chapter_id, ChapterStatus.in_progress, chapter=chapter),
        assembler.build_edit_prompt(chapter_id, story_id, state, instruction, context),
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
    state["pending_turn"] = {"content": "".join(chunks), "instruction": instruction, "source": "ai", "draft_id": str(uuid.uuid4()), "base_revision": state["manuscript_revision"], "scene_id": state.get("generation_scene_id"), "base_planning_revision": state.get("planning_revision", 0)}
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
async def apply_manual_edit(chapter_id: uuid.UUID, new_content: str, revision: int = 0, expected_version: int | None = None,
                            planning_revision: int = 0, detach_scene: bool = False) -> dict:
    """User hand-edits the pending draft directly — no model call."""
    state = await session_store.get_session(chapter_id)
    if expected_version is not None and expected_version != state["version"]:
        raise session_store.SessionConflict(chapter_id)
    if not new_content.strip() or len(new_content) > 50000:
        raise ValueError("Draft must contain between 1 and 50000 characters")
    scene_id = (state["pending_turn"] or {}).get("scene_id")
    state["pending_turn"] = {"content": new_content, "instruction": None, "source": "user_edit", "draft_id": str(uuid.uuid4()), "base_revision": revision,
                             "scene_id": None if detach_scene else scene_id, "base_planning_revision": planning_revision}
    await session_store.save_session(chapter_id, state)
    return state["pending_turn"]


@log_execution
async def accept_pending(db: AsyncSession, chapter: Chapter, background_tasks: BackgroundTasks, draft_id: uuid.UUID | None = None, actor_id: uuid.UUID | None = None) -> dict:
    chapter = await manuscript.lock_chapter(db, chapter)
    chapter_id = chapter.id
    if draft_id:
        existing = await db.scalar(select(ChapterTurn).where(ChapterTurn.chapter_id == chapter_id, ChapterTurn.accepted_draft_id == draft_id))
        if existing:
            return {"accepted": True, "sequence": existing.sequence, "turn": TurnRead.model_validate(existing).model_dump(mode="json")}
    state = await session_store.get_session(chapter_id)
    if state["pending_turn"] is None:
        raise ValueError("Nothing to accept")

    content = state["pending_turn"]["content"]
    instruction = state["pending_turn"]["instruction"]
    pending = state["pending_turn"]
    if draft_id and str(draft_id) != pending.get("draft_id"):
        raise HTTPException(409, "The pending draft changed. Reload before accepting.")
    if pending.get("base_revision", chapter.manuscript_revision) != chapter.manuscript_revision:
        raise HTTPException(409, "The manuscript changed after this draft was written. Review and save the draft, or regenerate it, before accepting.")
    if pending.get("base_planning_revision", 0) != chapter.planning_revision:
        raise HTTPException(409, "Planning changed after this draft was written. Review and save it, or regenerate it, before accepting.")
    scene_id = pending.get("scene_id")
    if scene_id:
        try:
            scene_id = uuid.UUID(scene_id)
        except ValueError as error:
            raise HTTPException(409, "The draft has an invalid scene reference. Review and save it again.") from error
        await planning.get_scene(db, chapter.id, scene_id)
    if not content.strip():
        raise ValueError("Cannot accept an empty paragraph")

    next_sequence = await db.scalar(
        select(func.coalesce(func.max(ChapterTurn.sequence), -1) + 1).where(ChapterTurn.chapter_id == chapter_id)
    )
    turn = ChapterTurn(chapter_id=chapter_id, sequence=next_sequence, content=content, instruction=instruction, source=pending.get("source", "ai"), version=1, scene_id=scene_id,
                       accepted_draft_id=uuid.UUID(pending["draft_id"]) if pending.get("draft_id") else None)
    db.add(turn)
    await db.flush()
    manuscript.record_revision(db, turn, actor_id)
    manuscript.changed(db, chapter, turn)
    chapter.status = ChapterStatus.in_progress
    await db.commit()
    await db.refresh(turn)

    # Accepted context now lives in PostgreSQL; keep Redis bounded to draft state.
    state["raw_tail"] = []
    state["running_summary"] = ""
    state["word_count_since_compaction"] = 0
    state["pending_turn"] = None
    state["sibling_attempts"] = []
    # Durable acceptance has succeeded. Redis failure cannot undo it or make a retry duplicate it.
    try:
        await session_store.save_session(chapter_id, state)
    except Exception:
        logger.warning("accepted paragraph saved; draft session cleanup failed for %s", chapter_id)
    return {"accepted": True, "sequence": next_sequence, "turn": TurnRead.model_validate(turn).model_dump(mode="json")}


@log_execution
async def discard_pending(db: AsyncSession, chapter: Chapter) -> None:
    chapter = await manuscript.lock_chapter(db, chapter)
    chapter_id = chapter.id
    state = await session_store.get_session(chapter_id)
    state["pending_turn"] = None
    await session_store.save_session(chapter_id, state)

    has_turns = await db.scalar(select(ChapterTurn.id).where(ChapterTurn.chapter_id == chapter_id).limit(1))
    new_status = ChapterStatus.in_progress if has_turns else ChapterStatus.draft
    await set_chapter_status(db, chapter_id, new_status, chapter=chapter)


@log_execution
async def complete_chapter(db: AsyncSession, chapter: Chapter, background_tasks: BackgroundTasks) -> dict:
    chapter = await manuscript.lock_chapter(db, chapter)
    chapter_id = chapter.id
    state = await session_store.get_session(chapter_id)
    if state["pending_turn"] is not None:
        pending_id = state["pending_turn"].get("draft_id")
        already_accepted = pending_id and await db.scalar(select(ChapterTurn.id).where(ChapterTurn.chapter_id == chapter_id, ChapterTurn.accepted_draft_id == uuid.UUID(pending_id)))
        # explicit rule: block, don't silently discard or include
        if not already_accepted:
            raise ValueError("Resolve the pending draft (accept or discard) before completing the chapter")

    chapter.status = ChapterStatus.complete
    db.add(BackgroundJob(kind="memory", target_id=chapter.id, target_revision=chapter.manuscript_revision))
    await db.commit()
    return {"status": "complete", "summarizing": True}
