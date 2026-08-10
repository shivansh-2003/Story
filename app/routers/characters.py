import uuid

from fastapi import APIRouter, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import Character, CharacterRelationship
from app.schemas import (
    CharacterCreate,
    CharacterRead,
    CharacterRelationshipCreate,
    CharacterRelationshipRead,
    CharacterUpdate,
)
from app.services import get_owned_character

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("", response_model=list[CharacterRead])
async def list_characters(db: DbSession, current_user: CurrentUser) -> list[Character]:
    result = await db.execute(
        select(Character).where(Character.user_id == current_user.id, Character.is_archived.is_(False))
    )
    return list(result.scalars().all())


@router.post("", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
async def create_character(body: CharacterCreate, db: DbSession, current_user: CurrentUser) -> Character:
    character = Character(user_id=current_user.id, **body.model_dump())
    db.add(character)
    await db.commit()
    await db.refresh(character)
    return character


@router.get("/{character_id}", response_model=CharacterRead)
async def get_character(character_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> Character:
    return await get_owned_character(db, character_id, current_user)


@router.patch("/{character_id}", response_model=CharacterRead)
async def update_character(
    character_id: uuid.UUID, body: CharacterUpdate, db: DbSession, current_user: CurrentUser
) -> Character:
    character = await get_owned_character(db, character_id, current_user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(character, field, value)
    await db.commit()
    await db.refresh(character)
    return character


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_character(character_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> None:
    character = await get_owned_character(db, character_id, current_user)
    character.is_archived = True
    await db.commit()


@router.get("/{character_id}/relationships", response_model=list[CharacterRelationshipRead])
async def list_relationships(
    character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> list[CharacterRelationship]:
    await get_owned_character(db, character_id, current_user)
    result = await db.execute(
        select(CharacterRelationship).where(CharacterRelationship.character_id == character_id)
    )
    return list(result.scalars().all())


@router.post(
    "/{character_id}/relationships",
    response_model=CharacterRelationshipRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_relationship(
    character_id: uuid.UUID, body: CharacterRelationshipCreate, db: DbSession, current_user: CurrentUser
) -> CharacterRelationship:
    await get_owned_character(db, character_id, current_user)
    await get_owned_character(db, body.related_character_id, current_user)

    relationship = CharacterRelationship(character_id=character_id, **body.model_dump())
    db.add(relationship)
    await db.commit()
    await db.refresh(relationship)
    return relationship
