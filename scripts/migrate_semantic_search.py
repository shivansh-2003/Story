"""Enables pgvector and adds the embedding column + similarity index to
chapter_turns, for semantic search over past chapters.

Idempotent — safe to run against a database that already has this applied.
Run via:
    PYTHONPATH=. .venv/bin/python scripts/migrate_semantic_search.py
"""

import asyncio

from sqlalchemy import text

from app.database import engine

STATEMENTS = [
    "CREATE EXTENSION IF NOT EXISTS vector",
    "ALTER TABLE chapter_turns ADD COLUMN IF NOT EXISTS embedding vector(1536)",
    # ivfflat needs a rough row-count estimate for `lists` — 100 is a
    # reasonable default for a single-app, low-thousands-of-rows table;
    # revisit if any one story's chapter_turns grows past ~100k rows.
    """
    CREATE INDEX IF NOT EXISTS ix_chapter_turns_embedding
    ON chapter_turns USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100)
    """,
]


async def migrate() -> None:
    async with engine.connect() as conn:
        autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        for stmt in STATEMENTS:
            print(f"-> {stmt}")
            await autocommit_conn.execute(text(stmt))
    print("semantic search migration applied")


if __name__ == "__main__":
    asyncio.run(migrate())
