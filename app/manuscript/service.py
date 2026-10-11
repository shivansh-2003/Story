import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.chapters.models import Chapter, ChapterStatus
from app.generation.models import ChapterTurn
from app.jobs.models import BackgroundJob
from app.manuscript.models import TurnRevision


async def lock_chapter(db: AsyncSession, chapter: Chapter) -> Chapter:
    chapter = await db.scalar(
        select(Chapter)
        .where(Chapter.id == chapter.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if chapter.status == ChapterStatus.locked:
        raise DomainError(409, "Chapter is locked — unlock it before changing text.")
    return chapter


async def get_turn(
    db: AsyncSession, chapter_id: uuid.UUID, turn_id: uuid.UUID
) -> ChapterTurn:
    turn = await db.scalar(
        select(ChapterTurn)
        .where(ChapterTurn.id == turn_id, ChapterTurn.chapter_id == chapter_id)
        .execution_options(populate_existing=True)
    )
    if turn is None:
        raise DomainError(404, "Paragraph not found")
    return turn


async def list_turns(db: AsyncSession, chapter_id: uuid.UUID) -> list[ChapterTurn]:
    return list(
        (
            await db.scalars(
                select(ChapterTurn)
                .where(ChapterTurn.chapter_id == chapter_id)
                .order_by(ChapterTurn.sequence)
            )
        ).all()
    )


async def list_revisions(db: AsyncSession, turn: ChapterTurn) -> list[TurnRevision]:
    return list(
        (
            await db.scalars(
                select(TurnRevision)
                .where(TurnRevision.turn_id == turn.id)
                .order_by(TurnRevision.revision_number.desc())
            )
        ).all()
    )


def record_revision(
    db: AsyncSession,
    turn: ChapterTurn,
    actor_id: uuid.UUID | None,
    restored_from: int | None = None,
) -> None:
    db.add(
        TurnRevision(
            turn_id=turn.id,
            revision_number=turn.version,
            content=turn.content,
            source=turn.source,
            actor_id=actor_id,
            restored_from=restored_from,
        )
    )


def changed(db: AsyncSession, chapter: Chapter, turn: ChapterTurn) -> None:
    chapter.manuscript_revision += 1
    chapter.memory_revision = None
    chapter.chapter_summary = None
    chapter.running_summary_cache = None
    turn.embedding = None
    turn.embedding_version = None
    db.add(
        BackgroundJob(
            kind="memory",
            target_id=chapter.id,
            target_revision=chapter.manuscript_revision,
        )
    )
    db.add(
        BackgroundJob(kind="embedding", target_id=turn.id, target_revision=turn.version)
    )


async def append_imported_paragraphs(
    db: AsyncSession,
    chapter: Chapter,
    paragraphs: list[str],
    actor_id: uuid.UUID,
    enrich_with_ai: bool,
) -> list[ChapterTurn]:
    """Append to a newly created chapter inside the caller's import transaction."""
    turns = []
    for sequence, content in enumerate(paragraphs):
        turn = ChapterTurn(
            id=uuid.uuid4(),
            chapter_id=chapter.id,
            sequence=sequence,
            content=content,
            version=1,
            source="import",
        )
        db.add(turn)
        record_revision(db, turn, actor_id)
        turns.append(turn)
    if turns:
        chapter.status = ChapterStatus.in_progress
        chapter.manuscript_revision = 1
        chapter.memory_revision = None
        if enrich_with_ai:
            db.add(
                BackgroundJob(kind="memory", target_id=chapter.id, target_revision=1)
            )
            for turn in turns:
                db.add(
                    BackgroundJob(
                        kind="embedding", target_id=turn.id, target_revision=1
                    )
                )
    return turns


async def stage_turn_edit(
    db: AsyncSession,
    chapter: Chapter,
    turn_id: uuid.UUID,
    content: str | None,
    expected_version: int,
    actor_id: uuid.UUID,
    revision_id: uuid.UUID | None = None,
    *,
    source: str = "user_edit",
) -> ChapterTurn:
    """Stage prose, history and derived jobs; the calling use case commits."""
    chapter = await lock_chapter(db, chapter)
    turn = await get_turn(db, chapter.id, turn_id)
    if turn.version != expected_version:
        raise DomainError(
            409,
            "This paragraph changed in another session. Reload it before saving; your edit has not been applied.",
        )
    restored_from = None
    if revision_id is not None:
        revision = await db.scalar(
            select(TurnRevision).where(
                TurnRevision.id == revision_id, TurnRevision.turn_id == turn.id
            )
        )
        if revision is None:
            raise DomainError(404, "Revision not found")
        content, restored_from = revision.content, revision.revision_number
    if content == turn.content:
        return turn
    # Lazy baseline also protects older databases that have not yet backfilled history.
    if not await db.scalar(
        select(TurnRevision.id).where(
            TurnRevision.turn_id == turn.id,
            TurnRevision.revision_number == turn.version,
        )
    ):
        record_revision(db, turn, None)
    turn.content = content
    turn.version += 1
    turn.source = "restore" if revision_id else source
    record_revision(db, turn, actor_id, restored_from)
    if chapter.status == ChapterStatus.complete:
        chapter.status = ChapterStatus.in_progress
    changed(db, chapter, turn)
    await db.flush()
    return turn


async def edit_turn(
    db: AsyncSession, chapter: Chapter, turn_id: uuid.UUID, content: str | None,
    expected_version: int, actor_id: uuid.UUID, revision_id: uuid.UUID | None = None,
) -> ChapterTurn:
    turn = await stage_turn_edit(db, chapter, turn_id, content, expected_version,
                                 actor_id, revision_id)
    await db.commit()
    await db.refresh(turn)
    return turn
