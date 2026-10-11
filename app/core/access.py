"""Domain ownership checks shared by feature services and API routes."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import Chapter
from app.characters.models import Character
from app.core.errors import DomainError
from app.stories.models import Story
from app.users.models import User


async def get_owned_story(db: AsyncSession, story_id: uuid.UUID, user: User, *, for_update: bool = False) -> Story:
    if for_update:
        story = await db.scalar(select(Story).where(Story.id == story_id).with_for_update()
                                .execution_options(populate_existing=True))
    else:
        story = await db.get(Story, story_id)
    if story is None or story.is_archived or story.user_id != user.id:
        raise DomainError(404, "Story not found")
    return story


async def get_owned_character(db: AsyncSession, character_id: uuid.UUID, user: User, *, for_update: bool = False) -> Character:
    if for_update:
        character = await db.scalar(
            select(Character).where(Character.id == character_id).with_for_update()
            .execution_options(populate_existing=True)
        )
    else:
        character = await db.get(Character, character_id)
    if character is None or character.is_archived or character.user_id != user.id:
        raise DomainError(404, "Character not found")
    return character


async def get_owned_chapter(db: AsyncSession, story_id: uuid.UUID, chapter_id: uuid.UUID, user: User) -> Chapter:
    # single joined query instead of a separate story-ownership round trip
    # followed by a chapter fetch — same checks, one Neon round trip.
    result = await db.execute(
        select(Chapter)
        .join(Story, Story.id == Chapter.story_id)
        .where(
            Chapter.id == chapter_id,
            Chapter.story_id == story_id,
            Chapter.is_archived.is_(False),
            Story.user_id == user.id,
            Story.is_archived.is_(False),
        )
    )
    chapter = result.scalar_one_or_none()
    if chapter is None:
        raise DomainError(404, "Chapter not found")
    return chapter
