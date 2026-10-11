import uuid

from fastapi import APIRouter, Query

from app.core.deps import (
    CurrentUser,
    DbSession,
    RateLimitedUser,
    get_owned_chapter,
    get_owned_story,
)
from app.planning import service, suggestions
from app.planning.schemas import (
    PlanRead,
    PlanUpdate,
    ProposalRead,
    ProposalSave,
    SceneFields,
    SceneRead,
    SceneReorder,
    SceneUpdate,
    SuggestionRequest,
)

router = APIRouter(prefix="/stories/{story_id}", tags=["planning"])


@router.get("/chapters/{chapter_id}/plan", response_model=PlanRead)
async def read_plan(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, user: CurrentUser
):
    return await service.plan_read(
        db, await get_owned_chapter(db, story_id, chapter_id, user)
    )


@router.patch("/chapters/{chapter_id}/plan", response_model=PlanRead)
async def update_plan(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: PlanUpdate,
    db: DbSession,
    user: CurrentUser,
):
    return await service.save_plan(
        db, await get_owned_chapter(db, story_id, chapter_id, user), body
    )


@router.get("/chapters/{chapter_id}/scenes")
async def scenes(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, user: CurrentUser
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    return {
        "scenes": await service.scenes_read(db, chapter),
        "planning_revision": chapter.planning_revision,
    }


@router.post("/chapters/{chapter_id}/scenes", response_model=SceneRead, status_code=201)
async def create_scene(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: SceneFields,
    db: DbSession,
    user: CurrentUser,
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    created = await service.create_scene(db, chapter, body)
    return next(s for s in await service.scenes_read(db, chapter) if s.id == created.id)


@router.patch("/chapters/{chapter_id}/scenes/reorder", status_code=204)
async def reorder(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: SceneReorder,
    db: DbSession,
    user: CurrentUser,
):
    await service.reorder_scenes(
        db, await get_owned_chapter(db, story_id, chapter_id, user), body
    )


@router.patch("/chapters/{chapter_id}/scenes/{scene_id}", response_model=SceneRead)
async def update_scene(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    scene_id: uuid.UUID,
    body: SceneUpdate,
    db: DbSession,
    user: CurrentUser,
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    await service.update_scene(db, chapter, scene_id, body)
    return next(s for s in await service.scenes_read(db, chapter) if s.id == scene_id)


@router.delete("/chapters/{chapter_id}/scenes/{scene_id}", status_code=204)
async def remove_scene(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    scene_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
    expected_version: int = Query(ge=1),
):
    await service.archive_scene(
        db,
        await get_owned_chapter(db, story_id, chapter_id, user),
        scene_id,
        expected_version,
    )


@router.post("/plan-suggestions", response_model=ProposalRead)
async def suggest(
    story_id: uuid.UUID, body: SuggestionRequest, db: DbSession, user: RateLimitedUser
):
    chapter = await get_owned_chapter(db, story_id, body.chapter_id, user)
    story = await get_owned_story(db, story_id, user)
    return await suggestions.suggest(db, chapter, story, body.instruction)


@router.post("/chapters/{chapter_id}/plan-proposals/save", response_model=PlanRead)
async def save_proposal(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: ProposalSave,
    db: DbSession,
    user: CurrentUser,
):
    return await service.save_proposal(
        db, await get_owned_chapter(db, story_id, chapter_id, user), body
    )
