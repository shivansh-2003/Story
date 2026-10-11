import uuid

from fastapi import APIRouter
from sqlalchemy import or_, select

from app.core.access import get_owned_chapter
from app.chapters.models import Chapter
from app.core.deps import CurrentUser, DbSession, RateLimitedUser
from app.generation.models import ChapterTurn
from app.jobs.models import BackgroundJob
from app.jobs.service import enqueue
from app.manuscript import service
from app.manuscript.schemas import RestoreRequest, RevisionRead, TurnRead, TurnUpdate

router = APIRouter(
    prefix="/stories/{story_id}/chapters/{chapter_id}", tags=["manuscript"]
)


@router.get("/turns", response_model=list[TurnRead])
async def turns(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, user: CurrentUser
):
    await get_owned_chapter(db, story_id, chapter_id, user)
    return await service.list_turns(db, chapter_id)


@router.patch("/turns/{turn_id}", response_model=TurnRead)
async def edit(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    turn_id: uuid.UUID,
    body: TurnUpdate,
    db: DbSession,
    user: CurrentUser,
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    return await service.edit_turn(
        db, chapter, turn_id, body.content, body.expected_version, user.id
    )


@router.get("/turns/{turn_id}/revisions", response_model=list[RevisionRead])
async def revisions(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    turn_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    await get_owned_chapter(db, story_id, chapter_id, user)
    return await service.list_revisions(
        db, await service.get_turn(db, chapter_id, turn_id)
    )


@router.post("/turns/{turn_id}/restore", response_model=TurnRead)
async def restore(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    turn_id: uuid.UUID,
    body: RestoreRequest,
    db: DbSession,
    user: CurrentUser,
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    return await service.edit_turn(
        db, chapter, turn_id, None, body.expected_version, user.id, body.revision_id
    )


@router.get("/memory-status")
async def memory_status(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, user: CurrentUser
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    job = await db.scalar(
        select(BackgroundJob)
        .where(
            BackgroundJob.kind == "memory",
            BackgroundJob.target_id == chapter.id,
            BackgroundJob.target_revision == chapter.manuscript_revision,
        )
        .order_by(BackgroundJob.created_at.desc())
    )
    return {
        "revision": chapter.manuscript_revision,
        "fresh": chapter.memory_revision == chapter.manuscript_revision,
        "status": job.status if job else "not_requested",
        "error": job.error if job else None,
    }


@router.post("/memory-refresh", status_code=202)
async def refresh_memory(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, user: RateLimitedUser
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    chapter = await db.scalar(
        select(Chapter)
        .where(Chapter.id == chapter.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    job = await enqueue(db, "memory", chapter.id, chapter.manuscript_revision)
    turns = await db.scalars(
        select(ChapterTurn).where(
            ChapterTurn.chapter_id == chapter.id,
            or_(
                ChapterTurn.embedding.is_(None),
                ChapterTurn.embedding_version.is_(None),
                ChapterTurn.embedding_version != ChapterTurn.version,
            ),
        )
    )
    for turn in turns:
        await enqueue(db, "embedding", turn.id, turn.version)
    await db.commit()
    return {"job_id": job.id}
