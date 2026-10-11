"""Shared cast reads used by generation and targeted rewriting."""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import Chapter, ChapterCharacter
from app.characters.models import Character, CharacterRelationship
from app.planning.models import SceneCharacter
from app.stories.models import Story, StoryCharacter


async def chapter_cast(db: AsyncSession, chapter_id: uuid.UUID, *, limit: int | None = None) -> list[Character]:
    query = (select(Character)
             .join(ChapterCharacter, ChapterCharacter.character_id == Character.id)
             .join(Chapter, Chapter.id == ChapterCharacter.chapter_id)
             .join(Story, Story.id == Chapter.story_id)
             .where(Chapter.id == chapter_id, Character.is_archived.is_(False),
                    Character.user_id == Story.user_id)
             .order_by(Character.name, Character.id))
    if limit is not None:
        query = query.limit(limit)
    return list((await db.scalars(query)).all())


async def scene_cast(db: AsyncSession, story_id: uuid.UUID, scene_id: uuid.UUID) -> list[Character]:
    query = (select(Character)
             .join(SceneCharacter, SceneCharacter.character_id == Character.id)
             .join(StoryCharacter, StoryCharacter.character_id == Character.id)
             .join(Story, Story.id == StoryCharacter.story_id)
             .where(SceneCharacter.scene_id == scene_id,
                    StoryCharacter.story_id == story_id,
                    Character.user_id == Story.user_id,
                    Character.is_archived.is_(False))
             .order_by(Character.name, Character.id))
    return list((await db.scalars(query)).all())


async def cast_relationships(db: AsyncSession, ids: list[uuid.UUID]) -> list[CharacterRelationship]:
    if not ids:
        return []
    return list((await db.scalars(
        select(CharacterRelationship).where(
            CharacterRelationship.character_id.in_(ids),
            CharacterRelationship.related_character_id.in_(ids),
        ).order_by(CharacterRelationship.id)
    )).all())
