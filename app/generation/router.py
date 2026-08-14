import json
import logging
import uuid
from collections.abc import AsyncIterator

from fastapi import APIRouter, BackgroundTasks, HTTPException, status
from fastapi.responses import StreamingResponse

from app.core.deps import CurrentUser, DbSession, get_owned_chapter
from app.generation import service
from app.generation.schemas import EditRequest, GenerateRequest, ManualEditRequest, TurnOut

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
    current_user: CurrentUser,
) -> StreamingResponse:
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    prompt, state = await service.prepare_continue(db, chapter_id, story_id, body.instruction, body.length)
    stream = service.generate_continue(prompt, state, chapter_id, body.instruction)
    return StreamingResponse(_sse(stream), media_type="text/event-stream")


@router.post("/generate/edit")
async def generate_edit(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: EditRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> StreamingResponse:
    """Regenerate against the current pending draft. Always acts on pending_turn
    as-is regardless of source (ai or user_edit) — this satisfies "don't
    discard hand-edits" without extra branching at the call site."""
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    try:
        prompt, state = await service.prepare_edit(db, chapter_id, story_id, body.instruction)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
    stream = service.edit_pending(prompt, state, chapter_id, body.instruction)
    return StreamingResponse(_sse(stream), media_type="text/event-stream")


@router.post("/manual-edit", response_model=TurnOut)
async def manual_edit(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: ManualEditRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    return await service.apply_manual_edit(chapter_id, body.content)


@router.post("/accept")
async def accept(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    try:
        return await service.accept_pending(db, chapter_id, background_tasks)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))


@router.post("/discard")
async def discard(story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> dict:
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    await service.discard_pending(chapter_id)
    return {"discarded": True}


@router.post("/complete")
async def complete(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    try:
        return await service.complete_chapter(db, chapter_id, background_tasks)
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(e))
