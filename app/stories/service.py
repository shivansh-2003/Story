import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.characters.models import Character
from app.core.deps import get_owned_character, get_owned_story
from app.stories.models import Story, StoryCharacter
from app.stories.schemas import StoryCreate, StoryUpdate
from app.users.models import User


async def list_stories(db: AsyncSession, user: User) -> list[Story]:
    result = await db.execute(
        select(Story).where(Story.user_id == user.id, Story.is_archived.is_(False))
    )
    return list(result.scalars().all())


async def create_story(db: AsyncSession, user: User, body: StoryCreate) -> Story:
    story = Story(user_id=user.id, **body.model_dump())
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


async def imported_characters(db: AsyncSession, story_id: uuid.UUID) -> list[Character]:
    result = await db.execute(
        select(Character).join(StoryCharacter, StoryCharacter.character_id == Character.id).where(
            StoryCharacter.story_id == story_id
        )
    )
    return list(result.scalars().all())


async def update_story(db: AsyncSession, user: User, story_id: uuid.UUID, body: StoryUpdate) -> Story:
    story = await get_owned_story(db, story_id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(story, field, value)
    await db.commit()
    await db.refresh(story)
    return story


async def archive_story(db: AsyncSession, user: User, story_id: uuid.UUID) -> None:
    story = await get_owned_story(db, story_id, user)
    story.is_archived = True
    await db.commit()


async def import_character(db: AsyncSession, user: User, story_id: uuid.UUID, character_id: uuid.UUID) -> None:
    await get_owned_story(db, story_id, user)
    await get_owned_character(db, character_id, user)

    existing = await db.get(StoryCharacter, {"story_id": story_id, "character_id": character_id})
    if existing is not None:
        return

    db.add(StoryCharacter(story_id=story_id, character_id=character_id))
    await db.commit()


async def remove_character(db: AsyncSession, user: User, story_id: uuid.UUID, character_id: uuid.UUID) -> None:
    await get_owned_story(db, story_id, user)

    link = await db.get(StoryCharacter, {"story_id": story_id, "character_id": character_id})
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not imported into this story")

    await db.delete(link)
    await db.commit()
