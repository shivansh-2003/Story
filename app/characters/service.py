import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.characters.models import Character, CharacterRelationship
from app.characters.schemas import CharacterCreate, CharacterRelationshipCreate, CharacterUpdate
from app.core.deps import get_owned_character
from app.users.models import User


async def list_characters(db: AsyncSession, user: User) -> list[Character]:
    result = await db.execute(
        select(Character).where(Character.user_id == user.id, Character.is_archived.is_(False))
    )
    return list(result.scalars().all())


async def create_character(db: AsyncSession, user: User, body: CharacterCreate) -> Character:
    character = Character(user_id=user.id, **body.model_dump())
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


async def update_character(
    db: AsyncSession, user: User, character_id: uuid.UUID, body: CharacterUpdate
) -> Character:
    character = await get_owned_character(db, character_id, user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(character, field, value)
    await db.commit()
    await db.refresh(character)
    return character


async def archive_character(db: AsyncSession, user: User, character_id: uuid.UUID) -> None:
    character = await get_owned_character(db, character_id, user)
    character.is_archived = True
    await db.commit()


async def list_relationships(
    db: AsyncSession, user: User, character_id: uuid.UUID
) -> list[CharacterRelationship]:
    await get_owned_character(db, character_id, user)
    result = await db.execute(
        select(CharacterRelationship).where(CharacterRelationship.character_id == character_id)
    )
    return list(result.scalars().all())


async def add_relationship(
    db: AsyncSession, user: User, character_id: uuid.UUID, body: CharacterRelationshipCreate
) -> CharacterRelationship:
    await get_owned_character(db, character_id, user)
    await get_owned_character(db, body.related_character_id, user)

    relationship = CharacterRelationship(character_id=character_id, **body.model_dump())
    db.add(relationship)
    await db.commit()
    await db.refresh(relationship)
    return relationship


async def list_relationships_among(
    db: AsyncSession, character_ids: list[uuid.UUID]
) -> list[CharacterRelationship]:
    """Relationships where both sides are in the given set — used by the
    generation assembler to surface only relationships relevant to characters
    actually active in the current chapter, not the writer's full cast."""
    if not character_ids:
        return []
    result = await db.execute(
        select(CharacterRelationship).where(
            CharacterRelationship.character_id.in_(character_ids),
            CharacterRelationship.related_character_id.in_(character_ids),
        )
    )
    return list(result.scalars().all())
