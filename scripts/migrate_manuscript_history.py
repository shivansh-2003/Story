"""Upgrade an existing Story database atomically, preserving a local manuscript snapshot.

Stop the backend first. Run: PYTHONPATH=. venv/bin/python scripts/migrate_manuscript_history.py
For a new empty database, use venv/bin/alembic upgrade head instead.
"""

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command
from app.database import engine
from scripts.baseline_existing_database import verify


def migrate(connection):
    names = set(inspect(connection).get_table_names())
    revision = (
        connection.scalar(text("SELECT version_num FROM alembic_version"))
        if "alembic_version" in names
        else None
    )
    if revision in {"0002_phase1", "0003_phase2", "0004_phase3", "0005_phase4"}:
        print("Manuscript history migration is already applied.")
        return
    if revision not in (None, "0001_baseline"):
        raise RuntimeError("Unexpected migration revision; inspect before upgrading.")
    if revision is None:
        verify(connection)
    connection.execute(
        text("LOCK TABLE chapters, chapter_turns IN ACCESS EXCLUSIVE MODE")
    )
    turns = [
        dict(row)
        for row in connection.execute(
            text("SELECT * FROM chapter_turns ORDER BY chapter_id, sequence")
        ).mappings()
    ]
    chapters = [
        dict(row)
        for row in connection.execute(
            text("SELECT id, chapter_summary, running_summary_cache FROM chapters")
        ).mappings()
    ]
    directory = Path("logs")
    directory.mkdir(exist_ok=True)
    backup = (
        directory
        / f"phase1-before-migration-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    fd = os.open(backup, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as stream:
        json.dump(
            {
                "saved_at": datetime.now(UTC).isoformat(),
                "turns": turns,
                "chapter_memory": chapters,
            },
            stream,
            default=str,
            ensure_ascii=False,
        )
    print(f"Local snapshot saved: {backup.resolve()} ({len(turns)} paragraphs).")
    config = Config("alembic.ini")
    config.attributes["connection"] = connection
    if revision is None:
        command.stamp(config, "0001_baseline")
    command.upgrade(config, "0002_phase1")
    current = [
        dict(row)
        for row in connection.execute(
            text("SELECT id, content FROM chapter_turns")
        ).mappings()
    ]
    if {str(row["id"]): row["content"] for row in current} != {
        str(row["id"]): row["content"] for row in turns
    }:
        raise RuntimeError("Manuscript verification failed; migration will roll back.")
    print("Manuscript schema and revision history applied; every accepted paragraph is unchanged.")


async def main():
    try:
        async with engine.begin() as connection:
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
