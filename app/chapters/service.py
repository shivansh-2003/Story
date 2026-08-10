import uuid

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import Chapter, ChapterCharacter, ChapterStatus
from app.chapters.schemas import ChapterCreate, ChapterReorderRequest, ChapterUpdate
from app.characters.models import Character
from app.core.deps import get_owned_chapter, get_owned_character, get_owned_story
from app.generation.models import ChapterTurn
from app.users.models import User


async def list_chapters(db: AsyncSession, user: User, story_id: uuid.UUID) -> list[Chapter]:
    await get_owned_story(db, story_id, user)
    result = await db.execute(
        select(Chapter)
        .where(Chapter.story_id == story_id, Chapter.is_archived.is_(False))
        .order_by(Chapter.order_index)
    )
    return list(result.scalars().all())


async def create_chapter(db: AsyncSession, user: User, story_id: uuid.UUID, body: ChapterCreate) -> Chapter:
    await get_owned_story(db, story_id, user)

    next_order_index = await db.scalar(
        select(func.coalesce(func.max(Chapter.order_index), -1) + 1).where(Chapter.story_id == story_id)
    )

    chapter = Chapter(story_id=story_id, order_index=next_order_index, **body.model_dump())
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


async def reorder_chapters(
    db: AsyncSession, user: User, story_id: uuid.UUID, body: ChapterReorderRequest
) -> None:
    await get_owned_story(db, story_id, user)

    for item in body.items:
        chapter = await get_owned_chapter(db, story_id, item.chapter_id, user)
        chapter.order_index = item.order_index

    await db.commit()


async def get_chapter_body(db: AsyncSession, chapter_id: uuid.UUID) -> str:
    result = await db.execute(
        select(ChapterTurn.content).where(ChapterTurn.chapter_id == chapter_id).order_by(ChapterTurn.sequence)
    )
    return "\n\n".join(result.scalars().all())


async def update_chapter(
    db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID, body: ChapterUpdate
) -> Chapter:
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(chapter, field, value)
    await db.commit()
    await db.refresh(chapter)
    return chapter


async def archive_chapter(db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID) -> None:
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    chapter.is_archived = True
    await db.commit()


async def add_active_character(
    db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID, character_id: uuid.UUID
) -> None:
    await get_owned_chapter(db, story_id, chapter_id, user)
    await get_owned_character(db, character_id, user)

    existing = await db.get(ChapterCharacter, {"chapter_id": chapter_id, "character_id": character_id})
    if existing is not None:
        return

    db.add(ChapterCharacter(chapter_id=chapter_id, character_id=character_id))
    await db.commit()


async def remove_active_character(
    db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID, character_id: uuid.UUID
) -> None:
    await get_owned_chapter(db, story_id, chapter_id, user)

    link = await db.get(ChapterCharacter, {"chapter_id": chapter_id, "character_id": character_id})
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not active in this chapter")

    await db.delete(link)
    await db.commit()


async def list_active_characters(db: AsyncSession, chapter_id: uuid.UUID) -> list[Character]:
    result = await db.execute(
        select(Character)
        .join(ChapterCharacter, ChapterCharacter.character_id == Character.id)
        .where(ChapterCharacter.chapter_id == chapter_id)
    )
    return list(result.scalars().all())


async def get_prior_chapter_summaries(
    db: AsyncSession, story_id: uuid.UUID, before_chapter_id: uuid.UUID
) -> list[str]:
    target_order = await db.scalar(select(Chapter.order_index).where(Chapter.id == before_chapter_id))
    result = await db.execute(
        select(Chapter.chapter_summary)
        .where(
            Chapter.story_id == story_id,
            Chapter.order_index < target_order,
            Chapter.chapter_summary.is_not(None),
        )
        .order_by(Chapter.order_index)
    )
    return list(result.scalars().all())


async def update_chapter_summary(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    *,
    chapter_summary: str | None = None,
    running_summary_cache: str | None = None,
) -> None:
    chapter = await db.get(Chapter, chapter_id)
    if chapter_summary is not None:
        chapter.chapter_summary = chapter_summary
    if running_summary_cache is not None:
        chapter.running_summary_cache = running_summary_cache
    await db.commit()


async def set_chapter_status(db: AsyncSession, chapter_id: uuid.UUID, new_status: ChapterStatus) -> None:
    chapter = await db.get(Chapter, chapter_id)
    chapter.status = new_status
    await db.commit()
