import uuid

from fastapi import APIRouter, status

from app.characters import service
from app.characters.models import Character, CharacterRelationship
from app.characters.schemas import (
    CharacterCreate,
    CharacterRead,
    CharacterRelationshipCreate,
    CharacterRelationshipRead,
    CharacterUpdate,
)
from app.core.deps import CurrentUser, DbSession, get_owned_character

router = APIRouter(prefix="/characters", tags=["characters"])


@router.get("", response_model=list[CharacterRead])
async def list_characters(db: DbSession, current_user: CurrentUser) -> list[Character]:
    return await service.list_characters(db, current_user)


@router.post("", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
async def create_character(body: CharacterCreate, db: DbSession, current_user: CurrentUser) -> Character:
    return await service.create_character(db, current_user, body)


@router.get("/{character_id}", response_model=CharacterRead)
async def get_character(character_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> Character:
    return await get_owned_character(db, character_id, current_user)


@router.patch("/{character_id}", response_model=CharacterRead)
async def update_character(
    character_id: uuid.UUID, body: CharacterUpdate, db: DbSession, current_user: CurrentUser
) -> Character:
    return await service.update_character(db, current_user, character_id, body)


@router.delete("/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_character(character_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> None:
    await service.archive_character(db, current_user, character_id)


@router.get("/{character_id}/relationships", response_model=list[CharacterRelationshipRead])
async def list_relationships(
    character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> list[CharacterRelationship]:
    return await service.list_relationships(db, current_user, character_id)


@router.post(
    "/{character_id}/relationships",
    response_model=CharacterRelationshipRead,
    status_code=status.HTTP_201_CREATED,
)
async def add_relationship(
    character_id: uuid.UUID, body: CharacterRelationshipCreate, db: DbSession, current_user: CurrentUser
) -> CharacterRelationship:
    return await service.add_relationship(db, current_user, character_id, body)
