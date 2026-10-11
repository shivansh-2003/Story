import json
import logging
import uuid
from collections.abc import AsyncIterator
from contextlib import aclosing

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.access import get_owned_chapter
from app.core.deps import CurrentUser, DbSession, RateLimitedUser
from app.generation import service
from app.generation.schemas import (
    AcceptRequest,
    EditRequest,
    GenerateRequest,
    ManualEditRequest,
    SelectAttemptRequest,
)
from app.generation.session_store import SessionConflict

router = APIRouter(prefix="/stories/{story_id}/chapters/{chapter_id}", tags=["generation"])

logger = logging.getLogger("story_assistant.generation")


async def _sse(stream: AsyncIterator[str]) -> AsyncIterator[str]:
    """Frames each chunk as an SSE `data:` line, JSON-encoded so embedded
    newlines in generated prose don't collide with the blank-line frame
    separator. Errors mid-stream can't become an HTTP error status — headers
    are already sent — so they're surfaced as an in-band {"error": ...} frame
    instead, after logging server-side since the client only sees the message."""
    try:
        async with aclosing(stream):
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
    return await service.read_session(db, chapter)

@router.post("/session/select")
async def select_attempt(story_id: uuid.UUID, chapter_id: uuid.UUID, body: SelectAttemptRequest, db: DbSession, current_user: CurrentUser) -> dict:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    return await service.select_attempt(db, chapter, body)

@router.post("/manual-edit")
async def manual_edit(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: ManualEditRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    return await service.save_manual_draft(db, chapter, body)

@router.post("/accept")
async def accept(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
    body: AcceptRequest = AcceptRequest(),
) -> dict:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    try:
        return await service.accept_pending(db, chapter, body.draft_id, current_user.id)
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
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    try:
        return await service.complete_chapter(db, chapter)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/resummarize")
async def resummarize(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Queue a durable summary refresh, retaining the existing API response."""
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    return await service.request_resummarize(db, chapter)
