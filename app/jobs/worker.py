import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, or_, select, update

from app.database import async_session
from app.generation.embedder import embed_turn
from app.jobs.models import BackgroundJob
from app.manuscript.memory import refresh_memory

logger = logging.getLogger(__name__)
MAX_ATTEMPTS = 3


async def run_one() -> bool:
    now = datetime.now(timezone.utc)
    async with async_session() as db:
        job = await db.scalar(
            select(BackgroundJob)
            .where(
                BackgroundJob.attempts < MAX_ATTEMPTS,
                or_(
                    and_(
                        BackgroundJob.status == "queued",
                        BackgroundJob.available_at <= now,
                    ),
                    and_(
                        BackgroundJob.status == "running",
                        BackgroundJob.lease_until < now,
                    ),
                ),
            )
            .order_by(BackgroundJob.created_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        if job is None:
            # A process killed during its final attempt must not leave a permanent running job.
            await db.execute(
                update(BackgroundJob)
                .where(
                    BackgroundJob.status == "running",
                    BackgroundJob.lease_until < now,
                    BackgroundJob.attempts >= MAX_ATTEMPTS,
                )
                .values(status="failed", error="Worker interrupted; retry refresh.")
            )
            await db.commit()
            return False
        job.status = "running"
        job.attempts += 1
        job.lease_until = now + timedelta(minutes=10)
        await db.commit()
        job_id, attempt = job.id, job.attempts

    # A heartbeat keeps long chapter summaries from being reclaimed mid-run.
    async def heartbeat():
        while True:
            await asyncio.sleep(60)
            async with async_session() as db:
                await db.execute(
                    update(BackgroundJob)
                    .where(
                        BackgroundJob.id == job_id,
                        BackgroundJob.attempts == attempt,
                        BackgroundJob.status == "running",
                    )
                    .values(
                        lease_until=datetime.now(timezone.utc) + timedelta(minutes=10)
                    )
                )
                await db.commit()

    pulse = asyncio.create_task(heartbeat())
    try:
        if job.kind == "memory":
            applied = await refresh_memory(job.target_id, job.target_revision)
        elif job.kind == "embedding":
            applied = await embed_turn(job.target_id, job.target_revision)
        else:
            raise ValueError("Unknown job type")
        values = {"status": "done" if applied else "obsolete", "error": None}
    except Exception as error:
        logger.warning("Background job %s failed (%s)", job_id, type(error).__name__)
        values = {
            "status": "failed" if attempt >= MAX_ATTEMPTS else "queued",
            "error": "AI memory refresh failed; check provider settings and retry.",
            "available_at": datetime.now(timezone.utc)
            + timedelta(seconds=30 * attempt),
        }
    finally:
        pulse.cancel()
        await asyncio.gather(pulse, return_exceptions=True)
    async with async_session() as db:
        await db.execute(
            update(BackgroundJob)
            .where(
                BackgroundJob.id == job_id,
                BackgroundJob.attempts == attempt,
                BackgroundJob.status == "running",
            )
            .values(**values, lease_until=None)
        )
        await db.commit()
    return True


async def run_worker():
    while True:
        try:
            if not await run_one():
                await asyncio.sleep(5)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Background worker unavailable")
            await asyncio.sleep(10)
