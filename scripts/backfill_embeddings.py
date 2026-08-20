"""One-time backfill for chapter_turns written before semantic search
shipped. Idempotent — only processes rows where embedding IS NULL, safe to
re-run if interrupted. Run via:
    PYTHONPATH=. .venv/bin/python scripts/backfill_embeddings.py
"""

import asyncio

from sqlalchemy import select

from app.database import async_session
from app.generation.embedder import embed_turn
from app.generation.models import ChapterTurn

PROGRESS_EVERY = 20


async def main() -> None:
    async with async_session() as db:
        result = await db.execute(select(ChapterTurn.id).where(ChapterTurn.embedding.is_(None)))
        turn_ids = list(result.scalars().all())

    print(f"backfilling {len(turn_ids)} turns")
    for i, turn_id in enumerate(turn_ids):
        await embed_turn(turn_id)
        if (i + 1) % PROGRESS_EVERY == 0:
            print(f"  {i + 1}/{len(turn_ids)}")
    print("backfill complete")


if __name__ == "__main__":
    asyncio.run(main())
