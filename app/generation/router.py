import uuid

from fastapi import APIRouter, BackgroundTasks, HTTPException, status

from app.core.deps import CurrentUser, DbSession, get_owned_chapter
from app.generation import service
from app.generation.schemas import EditRequest, GenerateRequest, ManualEditRequest, TurnOut

router = APIRouter(prefix="/stories/{story_id}/chapters/{chapter_id}", tags=["generation"])


@router.post("/generate", response_model=TurnOut)
async def generate(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: GenerateRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    return await service.generate_continue(db, chapter_id, story_id, body.instruction, body.length)


@router.post("/generate/edit", response_model=TurnOut)
async def generate_edit(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: EditRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> dict:
    """Regenerate against the current pending draft. Always acts on pending_turn
    as-is regardless of source (ai or user_edit) — this satisfies "don't
    discard hand-edits" without extra branching at the call site."""
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    return await service.edit_pending(db, chapter_id, story_id, body.instruction)


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
