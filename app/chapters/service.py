import uuid

from fastapi import BackgroundTasks, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import CHAPTER_TRANSITIONS, Chapter, ChapterCharacter, ChapterStatus
from app.chapters.schemas import ChapterCreate, ChapterReorderRequest, ChapterUpdate
from app.characters.models import Character
from app.characters.schemas import CharacterCreate
from app.characters.summarizer import summarize_character
from app.core.deps import get_owned_chapter, get_owned_character, get_owned_story
from app.core.logging_utils import log_execution
from app.core.status import assert_transition
from app.generation import session_store
from app.generation.models import ChapterTurn
from app.stories.models import Story
from app.users.models import User

# statuses reachable only through a dedicated endpoint (POST /complete,
# /lock) because they carry side effects a bare PATCH shouldn't trigger —
# summarization for complete, edit-protection for locked.
_PATCH_PROTECTED_STATUSES = {ChapterStatus.complete, ChapterStatus.locked}


@log_execution
async def list_chapters(db: AsyncSession, user: User, story_id: uuid.UUID) -> list[Chapter]:
    # single joined query instead of get_owned_story + a separate select —
    # LEFT JOIN from Story so a valid-but-empty story still returns exactly
    # one row (Chapter columns NULL), distinguishing it from a missing/
    # forbidden story (zero rows), preserving get_owned_story's 404 semantics
    # in one Neon round trip instead of two.
    result = await db.execute(
        select(Story.user_id, Story.is_archived, Chapter)
        .select_from(Story)
        .outerjoin(Chapter, (Chapter.story_id == Story.id) & (Chapter.is_archived.is_(False)))
        .where(Story.id == story_id)
        .order_by(Chapter.order_index)
    )
    rows = result.all()
    if not rows or rows[0].user_id != user.id or rows[0].is_archived:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Story not found")
    return [row.Chapter for row in rows if row.Chapter is not None]


@log_execution
async def create_chapter(db: AsyncSession, user: User, story_id: uuid.UUID, body: ChapterCreate) -> Chapter:
    await get_owned_story(db, story_id, user)

    next_order_index = await db.scalar(
        select(func.coalesce(func.max(Chapter.order_index), -1) + 1).where(Chapter.story_id == story_id)
    )

    chapter = Chapter(story_id=story_id, order_index=next_order_index, **body.model_dump())
    db.add(chapter)
    await db.commit()
    await db.refresh(chapter)
    return chapter


@log_execution
async def reorder_chapters(
    db: AsyncSession, user: User, story_id: uuid.UUID, body: ChapterReorderRequest
) -> None:
    await get_owned_story(db, story_id, user)

    chapter_ids = [item.chapter_id for item in body.items]
    result = await db.execute(
        select(Chapter).where(
            Chapter.story_id == story_id, Chapter.id.in_(chapter_ids), Chapter.is_archived.is_(False)
        )
    )
    chapters_by_id = {c.id: c for c in result.scalars().all()}

    ordered: list[tuple[Chapter, int]] = []
    for item in body.items:
        chapter = chapters_by_id.get(item.chapter_id)
        if chapter is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Chapter not found")
        ordered.append((chapter, item.order_index))

    # uq_chapter_order_per_story isn't deferrable, so Postgres checks it per
    # statement, not at commit. Writing final indices directly can collide
    # mid-transaction whenever two chapters swap positions — e.g. 0<->1: the
    # UPDATE claiming index 1 can run before the chapter currently there has
    # vacated it. Stage through temporary negative indices (always unique,
    # never overlap the real 0..n-1 range) so every row clears its old slot
    # before any row claims its new one.
    for i, (chapter, _) in enumerate(ordered):
        chapter.order_index = -(i + 1)
    await db.flush()
    for chapter, order_index in ordered:
        chapter.order_index = order_index

    await db.commit()


@log_execution
async def get_chapter_body(db: AsyncSession, chapter_id: uuid.UUID) -> str:
    # Rebuilt from chapter_turns on every read but only changes when a turn
    # is accepted, so it's cached in Redis and invalidated explicitly by
    # accept_pending — not a TTL-only cache.
    cached = await session_store.get_cached_chapter_body(chapter_id)
    if cached is not None:
        return cached
    result = await db.execute(
        select(ChapterTurn.content).where(ChapterTurn.chapter_id == chapter_id).order_by(ChapterTurn.sequence)
    )
    body = "\n\n".join(result.scalars().all())
    await session_store.set_cached_chapter_body(chapter_id, body)
    return body


@log_execution
async def update_chapter(
    db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID, body: ChapterUpdate
) -> Chapter:
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    fields = body.model_dump(exclude_unset=True)
    if "status" in fields:
        new_status = fields["status"]
        if new_status in _PATCH_PROTECTED_STATUSES and new_status != chapter.status:
            endpoint = "complete" if new_status == ChapterStatus.complete else "lock"
            raise HTTPException(
                status.HTTP_409_CONFLICT, f"Use the /{endpoint} endpoint to transition to {new_status.value}"
            )
        assert_transition(chapter.status, new_status, CHAPTER_TRANSITIONS)
    for field, value in fields.items():
        setattr(chapter, field, value)
    await db.commit()
    await db.refresh(chapter)
    return chapter


@log_execution
async def archive_chapter(db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID) -> None:
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    chapter.is_archived = True
    await db.commit()


@log_execution
async def add_active_character(
    db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID, character_id: uuid.UUID
) -> None:
    await get_owned_chapter(db, story_id, chapter_id, user)
    await get_owned_character(db, character_id, user)

    existing = await db.get(ChapterCharacter, {"chapter_id": chapter_id, "character_id": character_id})
    if existing is not None:
        return

    db.add(ChapterCharacter(chapter_id=chapter_id, character_id=character_id))
    await db.commit()


@log_execution
async def remove_active_character(
    db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID, character_id: uuid.UUID
) -> None:
    await get_owned_chapter(db, story_id, chapter_id, user)

    link = await db.get(ChapterCharacter, {"chapter_id": chapter_id, "character_id": character_id})
    if link is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Character not active in this chapter")

    await db.delete(link)
    await db.commit()


@log_execution
async def create_and_activate_character(
    db: AsyncSession,
    user: User,
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    body: CharacterCreate,
    background_tasks: BackgroundTasks,
) -> Character:
    """Create a character and mark it active in this chapter in one
    transaction — for "a new character just entered the scene," so the
    frontend doesn't have to sequence a create + an activate call."""
    await get_owned_chapter(db, story_id, chapter_id, user)

    character = Character(user_id=user.id, **body.model_dump())
    db.add(character)
    await db.flush()  # assign character.id before the link row needs it

    db.add(ChapterCharacter(chapter_id=chapter_id, character_id=character.id))
    await db.commit()
    await db.refresh(character)
    background_tasks.add_task(summarize_character, character.id)
    return character


@log_execution
async def list_active_characters(db: AsyncSession, chapter_id: uuid.UUID) -> list[Character]:
    # TODO: call log_cache_event here once a cache layer exists for this
    # lookup — per the backend optimization plan, this is a caching
    # candidate (queried on every prompt build within a chapter's writing
    # session, changes only when the active cast is edited).
    result = await db.execute(
        select(Character)
        .join(ChapterCharacter, ChapterCharacter.character_id == Character.id)
        .where(ChapterCharacter.chapter_id == chapter_id)
    )
    return list(result.scalars().all())


@log_execution
async def get_prior_chapter_summaries(
    db: AsyncSession, story_id: uuid.UUID, before_chapter_id: uuid.UUID
) -> list[str]:
    target_order = await db.scalar(select(Chapter.order_index).where(Chapter.id == before_chapter_id))
    result = await db.execute(
        select(Chapter.chapter_summary)
        .where(
            Chapter.story_id == story_id,
            Chapter.order_index < target_order,
            Chapter.chapter_summary.is_not(None),
        )
        .order_by(Chapter.order_index)
    )
    return list(result.scalars().all())


@log_execution
async def update_chapter_summary(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    *,
    chapter_summary: str | None = None,
    running_summary_cache: str | None = None,
) -> None:
    chapter = await db.get(Chapter, chapter_id)
    if chapter_summary is not None:
        chapter.chapter_summary = chapter_summary
    if running_summary_cache is not None:
        chapter.running_summary_cache = running_summary_cache
    await db.commit()


@log_execution
async def set_chapter_status(
    db: AsyncSession, chapter_id: uuid.UUID, new_status: ChapterStatus, chapter: Chapter | None = None
) -> None:
    if chapter is None:
        chapter = await db.get(Chapter, chapter_id)
    assert_transition(chapter.status, new_status, CHAPTER_TRANSITIONS)
    chapter.status = new_status
    await db.commit()


@log_execution
async def lock_chapter(db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID) -> None:
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    await set_chapter_status(db, chapter_id, ChapterStatus.locked, chapter=chapter)


@log_execution
async def unlock_chapter(db: AsyncSession, user: User, story_id: uuid.UUID, chapter_id: uuid.UUID) -> None:
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    await set_chapter_status(db, chapter_id, ChapterStatus.complete, chapter=chapter)
