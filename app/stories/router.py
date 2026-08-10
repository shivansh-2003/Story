import uuid

from fastapi import APIRouter, status

from app.core.deps import CurrentUser, DbSession, get_owned_story
from app.stories import service
from app.stories.models import Story
from app.stories.schemas import StoryCreate, StoryDetailRead, StoryRead, StoryUpdate

router = APIRouter(prefix="/stories", tags=["stories"])


@router.get("", response_model=list[StoryRead])
async def list_stories(db: DbSession, current_user: CurrentUser) -> list[Story]:
    return await service.list_stories(db, current_user)


@router.post("", response_model=StoryRead, status_code=status.HTTP_201_CREATED)
async def create_story(body: StoryCreate, db: DbSession, current_user: CurrentUser) -> Story:
    return await service.create_story(db, current_user, body)


@router.get("/{story_id}", response_model=StoryDetailRead)
async def get_story(story_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> StoryDetailRead:
    story = await get_owned_story(db, story_id, current_user)
    characters = await service.imported_characters(db, story_id)
    return StoryDetailRead.model_validate(story, from_attributes=True).model_copy(
        update={"characters": characters}
    )


@router.patch("/{story_id}", response_model=StoryRead)
async def update_story(
    story_id: uuid.UUID, body: StoryUpdate, db: DbSession, current_user: CurrentUser
) -> Story:
    return await service.update_story(db, current_user, story_id, body)


@router.delete("/{story_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_story(story_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> None:
    await service.archive_story(db, current_user, story_id)


@router.post("/{story_id}/characters", status_code=status.HTTP_204_NO_CONTENT)
async def import_character(
    story_id: uuid.UUID, character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await service.import_character(db, current_user, story_id, character_id)


@router.delete("/{story_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_character(
    story_id: uuid.UUID, character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await service.remove_character(db, current_user, story_id, character_id)
