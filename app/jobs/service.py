import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.jobs.models import BackgroundJob


async def enqueue(
    db: AsyncSession, kind: str, target_id: uuid.UUID, revision: int
) -> BackgroundJob:
    """Deduplicate explicit retries while a matching job is already pending."""
    job = await db.scalar(
        select(BackgroundJob).where(
            BackgroundJob.kind == kind,
            BackgroundJob.target_id == target_id,
            BackgroundJob.target_revision == revision,
            BackgroundJob.status.in_(["queued", "running"]),
        )
    )
    if job is None:
        job = BackgroundJob(kind=kind, target_id=target_id, target_revision=revision)
        db.add(job)
    return job
