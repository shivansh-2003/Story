import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.deps import CurrentUser, DbSession
from app.models import Chapter, ChapterCharacter
from app.schemas import ChapterCreate, ChapterDetailRead, ChapterRead, ChapterReorderRequest, ChapterUpdate
from app.services import get_chapter_body, get_owned_character, get_owned_chapter, get_owned_story

router = APIRouter(prefix="/stories/{story_id}/chapters", tags=["chapters"])


@router.get("", response_model=list[ChapterRead])
async def list_chapters(story_id: uuid.UUID, db: DbSession, current_user: CurrentUser) -> list[Chapter]:
    await get_owned_story(db, story_id, current_user)
    result = await db.execute(
        select(Chapter)
        .where(Chapter.story_id == story_id, Chapter.is_archived.is_(False))
        .order_by(Chapter.order_index)
    )
    return list(result.scalars().all())


@router.post("", response_model=ChapterRead, status_code=status.HTTP_201_CREATED)
async def create_chapter(
    story_id: uuid.UUID, body: ChapterCreate, db: DbSession, current_user: CurrentUser
) -> Chapter:
    await get_owned_story(db, story_id, current_user)

    next_order_index = await db.scalar(
        select(func.coalesce(func.max(Chapter.order_index), -1) + 1).where(Chapter.story_id == story_id)
    )

    chapter = Chapter(story_id=story_id, order_index=next_order_index, **body.model_dump())
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


@router.patch("/reorder", status_code=status.HTTP_204_NO_CONTENT)
async def reorder_chapters(
    story_id: uuid.UUID, body: ChapterReorderRequest, db: DbSession, current_user: CurrentUser
) -> None:
    await get_owned_story(db, story_id, current_user)

    for item in body.items:
        chapter = await get_owned_chapter(db, story_id, item.chapter_id, current_user)
        chapter.order_index = item.order_index

    await db.commit()


@router.get("/{chapter_id}", response_model=ChapterDetailRead)
async def get_chapter(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> ChapterDetailRead:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    body_text = await get_chapter_body(db, chapter_id)
    return ChapterDetailRead.model_validate(chapter, from_attributes=True).model_copy(
        update={"body": body_text}
    )


@router.patch("/{chapter_id}", response_model=ChapterRead)
async def update_chapter(
    story_id: uuid.UUID, chapter_id: uuid.UUID, body: ChapterUpdate, db: DbSession, current_user: CurrentUser
) -> Chapter:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(chapter, field, value)
    await db.commit()
    await db.refresh(chapter)
    return chapter


@router.delete("/{chapter_id}", status_code=status.HTTP_204_NO_CONTENT)
async def archive_chapter(
    story_id: uuid.UUID, chapter_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    chapter = await get_owned_chapter(db, story_id, chapter_id, current_user)
    chapter.is_archived = True
    await db.commit()


@router.post("/{chapter_id}/characters", status_code=status.HTTP_204_NO_CONTENT)
async def add_active_character(
    story_id: uuid.UUID, chapter_id: uuid.UUID, character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await get_owned_chapter(db, story_id, chapter_id, current_user)
    await get_owned_character(db, character_id, current_user)

    existing = await db.get(ChapterCharacter, {"chapter_id": chapter_id, "character_id": character_id})
    if existing is not None:
        return

    db.add(ChapterCharacter(chapter_id=chapter_id, character_id=character_id))
    await db.commit()


@router.delete("/{chapter_id}/characters/{character_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_active_character(
    story_id: uuid.UUID, chapter_id: uuid.UUID, character_id: uuid.UUID, db: DbSession, current_user: CurrentUser
) -> None:
    await get_owned_chapter(db, story_id, chapter_id, current_user)

    link = await db.get(ChapterCharacter, {"chapter_id": chapter_id, "character_id": character_id})
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not active in this chapter")

    await db.delete(link)
    await db.commit()
