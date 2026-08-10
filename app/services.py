import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Chapter, ChapterTurn, Character, Story, TurnStatus, User

INCLUDED_TURN_STATUSES = (TurnStatus.accepted, TurnStatus.edited)


async def get_owned_story(db: AsyncSession, story_id: uuid.UUID, user: User) -> Story:
    story = await db.get(Story, story_id)
    if story is None or story.is_archived or story.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Story not found")
    return story


async def get_owned_character(db: AsyncSession, character_id: uuid.UUID, user: User) -> Character:
    character = await db.get(Character, character_id)
    if character is None or character.is_archived or character.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not found")
    return character


async def get_owned_chapter(db: AsyncSession, story_id: uuid.UUID, chapter_id: uuid.UUID, user: User) -> Chapter:
    await get_owned_story(db, story_id, user)
    chapter = await db.get(Chapter, chapter_id)
    if chapter is None or chapter.is_archived or chapter.story_id != story_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
    return chapter


async def get_chapter_body(db: AsyncSession, chapter_id: uuid.UUID) -> str:
    result = await db.execute(
        select(ChapterTurn.content)
        .where(ChapterTurn.chapter_id == chapter_id, ChapterTurn.status.in_(INCLUDED_TURN_STATUSES))
        .order_by(ChapterTurn.created_at)
    )
    return "".join(result.scalars().all())
