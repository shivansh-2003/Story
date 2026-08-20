import uuid

from fastapi import APIRouter, BackgroundTasks, status

from app.chapters import service
from app.chapters.models import Chapter
from app.chapters.schemas import ChapterCreate, ChapterDetailRead, ChapterRead, ChapterReorderRequest, ChapterUpdate
from app.characters.models import Character
from app.characters.schemas import CharacterCreate, CharacterRead
from app.core.deps import CurrentUser, DbSession, get_owned_chapter

router = APIRouter(prefix="/stories/{story_id}/chapters", tags=["chapters"])


@router.get("", response_model=list[ChapterRead])
async def list_chapters(story_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> list[Chapter]:
    return await service.list_chapters(db, current_user, story_id)


@router.post("", response_model=ChapterRead, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    story_id: uuid.UUID, body: ChapterCreate, db: DbSession, current_user: CurrentUser
) -> Chapter:
    return await service.create_chapter(db, current_user, story_id, body)


@router.patch("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_chapters(
    story_id: uuid.UUID, body: ChapterReorderRequest, db: DbSession, current_user: CurrentUser
) -> None:
    await service.reorder_chapters(db, current_user, story_id, body)


@router.get("/{chapter_id}", response_model=ChapterDetailRead)
async def get_chapter(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> ChapterDetailRead:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    body_text = await service.get_chapter_body(db, chapter_id)
    return ChapterDetailRead.model_validate(chapter, from_attributes=True).model_copy(
        update={"body": body_text}
    )


@router.patch("/{chapter_id}", response_model=ChapterRead)
async def update_chapter(
    story_id: uuid.UUID, chapter_id: uuid.UUID, body: ChapterUpdate, db: DbSession, current_user: CurrentUser
) -> Chapter:
    return await service.update_chapter(db, current_user, story_id, chapter_id, body)


@router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_chapter(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await service.archive_chapter(db, current_user, story_id, chapter_id)


@router.post("/{chapter_id}/characters/new", response_model=CharacterRead, status_code=status.HTTP_201_CREATED)
async def create_and_activate_character(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: CharacterCreate,
    db: DbSession,
    current_user: CurrentUser,
    background_tasks: BackgroundTasks,
) -> Character:
    return await service.create_and_activate_character(
        db, current_user, story_id, chapter_id, body, background_tasks
    )


@router.post("/{chapter_id}/characters", status_code=status.HTTP_204_NO_CONTENT)
async def add_active_character(
    story_id: uuid.UUID, chapter_id: uuid.UUID, character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await service.add_active_character(db, current_user, story_id, chapter_id, character_id)


@router.delete("/{chapter_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_active_character(
    story_id: uuid.UUID, chapter_id: uuid.UUID, character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await service.remove_active_character(db, current_user, story_id, chapter_id, character_id)


@router.post("/{chapter_id}/lock", status_code=status.HTTP_204_NO_CONTENT)
async def lock_chapter(story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> None:
    """Deliberately a dedicated endpoint, not a PATCH status write — locking
    is meant to be a visible, intentional act, not a side effect of a bulk
    field update."""
    await service.lock_chapter(db, current_user, story_id, chapter_id)


@router.post("/{chapter_id}/unlock", status_code=status.HTTP_204_NO_CONTENT)
async def unlock_chapter(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await service.unlock_chapter(db, current_user, story_id, chapter_id)
