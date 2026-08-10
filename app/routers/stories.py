import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from app.deps import CurrentUser, DbSession
from app.models import Character, Story, StoryCharacter
from app.schemas import StoryCreate, StoryDetailRead, StoryRead, StoryUpdate
from app.services import get_owned_character, get_owned_story

router = APIRouter(prefix="/stories", tags=["stories"])


async def _imported_characters(db: DbSession, story_id: uuid.UUID) -> list[Character]:
    result = await db.execute(
        select(Character).join(StoryCharacter, StoryCharacter.character_id == Character.id).where(
            StoryCharacter.story_id == story_id
        )
    )
    return list(result.scalars().all())


@router.get("", response_model=list[StoryRead])
async def list_stories(db: DbSession, current_user: CurrentUser) -> list[Story]:
    result = await db.execute(
        select(Story).where(Story.user_id == current_user.id, Story.is_archived.is_(False))
    )
    return list(result.scalars().all())


@router.post("", response_model=StoryRead, status_code=status.HTTP_201_CREATED)
async def create_story(body: StoryCreate, db: DbSession, current_user: CurrentUser) -> Story:
    story = Story(user_id=current_user.id, **body.model_dump())
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


@router.get("/{story_id}", response_model=StoryDetailRead)
async def get_story(story_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> StoryDetailRead:
    story = await get_owned_story(db, story_id, current_user)
    characters = await _imported_characters(db, story_id)
    return StoryDetailRead.model_validate(story, from_attributes=True).model_copy(
        update={"characters": characters}
    )


@router.patch("/{story_id}", response_model=StoryRead)
async def update_story(
    story_id: uuid.UUID, body: StoryUpdate, db: DbSession, current_user: CurrentUser
) -> Story:
    story = await get_owned_story(db, story_id, current_user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(story, field, value)
    await db.commit()
    await db.refresh(story)
    return story


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_story(story_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> None:
    story = await get_owned_story(db, story_id, current_user)
    story.is_archived = True
    await db.commit()


@router.post("/{story_id}/characters", status_code=status.HTTP_204_NO_CONTENT)
async def import_character(
    story_id: uuid.UUID, character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await get_owned_story(db, story_id, current_user)
    await get_owned_character(db, character_id, current_user)

    existing = await db.get(StoryCharacter, {"story_id": story_id, "character_id": character_id})
    if existing is not None:
        return

    db.add(StoryCharacter(story_id=story_id, character_id=character_id))
    await db.commit()


@router.delete("/{story_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_character(
    story_id: uuid.UUID, character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await get_owned_story(db, story_id, current_user)

    link = await db.get(StoryCharacter, {"story_id": story_id, "character_id": character_id})
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not imported into this story")

    await db.delete(link)
    await db.commit()
