"""Compatibility entry points; durable memory jobs replace Redis-derived summaries."""
import uuid

from app.chapters.models import Chapter
from app.database import async_session
from app.jobs.models import BackgroundJob

COMPACTION_WORD_THRESHOLD = 700


async def maybe_compact_session(chapter_id: uuid.UUID) -> None:
    await summarize_completed_chapter(chapter_id)


async def summarize_completed_chapter(chapter_id: uuid.UUID) -> None:
    async with async_session() as db:
        chapter = await db.get(Chapter, chapter_id)
        if chapter is not None:
            db.add(BackgroundJob(kind="memory", target_id=chapter_id, target_revision=chapter.manuscript_revision))
            await db.commit()
