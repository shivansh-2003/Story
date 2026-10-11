import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select

from app.core.deps import CurrentUser, DbSession, RateLimitedUser, get_owned_chapter
from app.generation import service, session_store, summarizer
from app.generation.models import ChapterTurn
from app.generation.schemas import (
    AcceptRequest,
    EditRequest,
    GenerateRequest,
    ManualEditRequest,
    SelectAttemptRequest,
)
from app.generation.session_store import SessionConflict
from app.manuscript.service import lock_chapter
from app.planning import service as planning

router = APIRouter(prefix="/stories/{story_id}/chapters/{chapter_id}", tags=["generation"])

logger = logging.getLogger("story_assistant.generation")


async def _sse(stream: AsyncIterator[str]) -> AsyncIterator[str]:
    """Frames each chunk as an SSE `data:` line, JSON-encoded so embedded
    newlines in generated prose don't collide with the blank-line frame
    separator. Errors mid-stream can't become an HTTP error status — headers
    are already sent — so they're surfaced as an in-band {"error": ...} frame
    instead, after logging server-side since the client only sees the message."""
    try:
        async for delta in stream:
            yield f"data: {json.dumps({'delta': delta})}\n\n"
        yield f"data: {json.dumps({'done': True})}\n\n"
    except Exception as e:
        logger.exception("generation stream failed")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"


@router.post("/generate")
async def generate(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: GenerateRequest,
    db: DbSession,
    current_user: RateLimitedUser,
) -> StreamingResponse:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    system, user, state = await service.prepare_continue(db, chapter, story_id, body.instruction, body.length, body.scene_id)
    stream = service.generate_continue(system, user, state, chapter_id, body.instruction, body.length)
    return StreamingResponse(_sse(stream), media_type="text/event-stream")


@router.post("/generate/edit")
async def generate_edit(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: EditRequest,
    db: DbSession,
    current_user: RateLimitedUser,
) -> StreamingResponse:
    """Regenerate against the current pending draft. Always acts on pending_turn
    as-is regardless of source (ai or user_edit) — this satisfies "don't
    discard hand-edits" without extra branching at the call site."""
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    try:
        system, user, state = await service.prepare_edit(db, chapter, story_id, body.instruction)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    stream = service.edit_pending(system, user, state, chapter_id, body.instruction)
    return StreamingResponse(_sse(stream), media_type="text/event-stream")


@router.get("/session")
async def session(story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> dict:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    # Upgrade legacy Redis drafts lazily without discarding their contents.
    for _ in range(3):
        state = await session_store.get_session(chapter_id)
        migrated = False
        for draft in ([state["pending_turn"]] if state["pending_turn"] else []) + state["sibling_attempts"]:
            if not draft.get("draft_id"):
                draft["draft_id"] = str(uuid.uuid4())
                # Revision zero is the only safe basis for pre-versioning drafts.
                draft["base_revision"] = 0
                migrated = True
        if not migrated:
            break
        try:
            await session_store.save_session(chapter_id, state)
            break
        except SessionConflict:
            continue
    else:
        raise HTTPException(409, "The draft changed in another session. Reload first.")
    # Hide already-accepted drafts after a Redis cleanup failure.
    accepted_ids = {str(value) for value in (await db.scalars(select(ChapterTurn.accepted_draft_id).where(ChapterTurn.chapter_id == chapter_id, ChapterTurn.accepted_draft_id.is_not(None)))).all()}
    pending = state["pending_turn"]
    if pending and pending.get("draft_id") in accepted_ids:
        pending = None
    return {"pending_turn": pending, "sibling_attempts": [t for t in state["sibling_attempts"] if t.get("draft_id") not in accepted_ids], "version": state["version"], "manuscript_revision": chapter.manuscript_revision,
            "planning_revision": chapter.planning_revision,
            "stale_draft": bool(pending and (pending.get("base_revision", chapter.manuscript_revision) != chapter.manuscript_revision or pending.get("base_planning_revision", 0) != chapter.planning_revision))}


@router.post("/session/select")
async def select_attempt(story_id: uuid.UUID, chapter_id: uuid.UUID, body: SelectAttemptRequest, db: DbSession, current_user: CurrentUser) -> dict:
    chapter = await lock_chapter(db, await get_owned_chapter(db, story_id, chapter_id, current_user))
    state = await session_store.get_session(chapter_id)
    if state["version"] != body.expected_version:
        raise HTTPException(409, "The draft changed in another session. Reload first.")
    selected = next((t for t in state["sibling_attempts"] if t.get("draft_id") == str(body.draft_id)), None)
    if selected is None:
        raise HTTPException(404, "Attempt not found")
    attempts = [t for t in state["sibling_attempts"] if t is not selected]
    if state["pending_turn"]:
        attempts.insert(0, state["pending_turn"])
    state["pending_turn"], state["sibling_attempts"] = selected, attempts[:3]
    try:
        await session_store.save_session(chapter.id, state)
    except SessionConflict:
        raise HTTPException(409, "The draft changed in another session. Reload first.")
    return {"selected": True}


@router.post("/manual-edit")
async def manual_edit(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: ManualEditRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    chapter = await lock_chapter(db, await get_owned_chapter(db, story_id, chapter_id, current_user))
    state = await session_store.get_session(chapter_id)
    scene_id = (state["pending_turn"] or {}).get("scene_id")
    detach_scene = False
    if scene_id:
        try:
            await planning.get_scene(db, chapter.id, uuid.UUID(scene_id))
        except (HTTPException, ValueError):
            detach_scene = True
    try:
        return await service.apply_manual_edit(chapter_id, body.content, chapter.manuscript_revision, body.expected_version,
                                               chapter.planning_revision, detach_scene)
    except ValueError as error:
        raise HTTPException(400, str(error))
    except SessionConflict:
        raise HTTPException(409, "The draft changed in another session. Reload first.")


@router.post("/accept")
async def accept(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
    body: AcceptRequest = AcceptRequest(),
) -> dict:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    try:
        return await service.accept_pending(db, chapter, background_tasks, body.draft_id, current_user.id)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    except SessionConflict:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This chapter was updated in another tab or session — refresh and try again.",
        )


@router.post("/discard")
async def discard(story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> dict:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    try:
        await service.discard_pending(db, chapter)
    except SessionConflict:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This chapter was updated in another tab or session — refresh and try again.",
        )
    return {"discarded": True}


@router.post("/complete")
async def complete(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    try:
        return await service.complete_chapter(db, chapter, background_tasks)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/resummarize")
async def resummarize(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Manual escape hatch for a chapter_summary that never landed (e.g. the
    LLM call failed after retries exhausted) — re-runs the same background
    job /complete already schedules. Safe to call on any chapter regardless
    of current status; the job falls back to reconstructing from durable
    chapter_turns when there's no live Redis session to summarize from."""
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    background_tasks.add_task(summarizer.summarize_completed_chapter, chapter_id)
    return {"summarizing": True}
