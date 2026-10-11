import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.access import get_owned_character
from app.characters.models import Character, CharacterRelationship
from app.characters.schemas import CharacterCreate, CharacterRelationshipCreate, CharacterUpdate
from app.characters.summarizer import schedule_summary, should_resummarize

from app.core.logging_utils import log_execution
from app.users.models import User


@log_execution
async def list_characters(db: AsyncSession, user: User) -> list[Character]:
    result = await db.execute(
        select(Character).where(Character.user_id == user.id, Character.is_archived.is_(False))
    )
    return list(result.scalars().all())


@log_execution
async def create_character(
    db: AsyncSession, user: User, body: CharacterCreate
) -> Character:
    character = Character(id=uuid.uuid4(), user_id=user.id, **body.model_dump())
    db.add(character)
    schedule_summary(db, character)
    await db.commit()
    await db.refresh(character)
    return character


@log_execution
async def update_character(
    db: AsyncSession, user: User, character_id: uuid.UUID, body: CharacterUpdate
) -> Character:
    character = await get_owned_character(db, character_id, user, for_update=True)
    fields = {key: value for key, value in body.model_dump(exclude_unset=True).items()
              if getattr(character, key) != value}
    for field, value in fields.items():
        setattr(character, field, value)
    if should_resummarize(set(fields)):
        schedule_summary(db, character)
    await db.commit()
    await db.refresh(character)
    return character


@log_execution
async def archive_character(db: AsyncSession, user: User, character_id: uuid.UUID) -> None:
    character = await get_owned_character(db, character_id, user, for_update=True)
    character.is_archived = True
    await db.commit()


@log_execution
async def list_relationships(
    db: AsyncSession, user: User, character_id: uuid.UUID
) -> list[CharacterRelationship]:
    await get_owned_character(db, character_id, user)
    result = await db.execute(
        select(CharacterRelationship).where(CharacterRelationship.character_id == character_id)
    )
    return list(result.scalars().all())


@log_execution
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
