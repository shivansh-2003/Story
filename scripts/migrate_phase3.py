"""Upgrade Phase 2 to Phase 3 with a private snapshot and row-preservation checks."""

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command
from app.database import engine
from scripts.migrate_phase2 import canonical, read_tables


def migrate(connection):
    schema = connection.scalar(text("SELECT current_schema()"))
    quote = connection.dialect.identifier_preparer.quote_identifier
    revision = connection.scalar(
        text(f"SELECT version_num FROM {quote(schema)}.alembic_version")
    )
    if revision in {"0004_phase3", "0005_phase4"}:
        print("Phase 3 is already applied.")
        return
    if revision != "0003_phase2":
        raise RuntimeError("Phase 2 must be migrated first. No changes applied.")
    names = sorted(inspect(connection).get_table_names(schema=schema))
    if any(name in names for name in ("chapter_plans", "scenes", "scene_characters")):
        raise RuntimeError(
            "Unexpected planning tables already exist. Inspect schema drift first."
        )
    connection.execute(
        text(
            "LOCK TABLE "
            + ", ".join(f"{quote(schema)}.{quote(name)}" for name in names)
            + " IN SHARE ROW EXCLUSIVE MODE"
        )
    )
    before = read_tables(connection, names, schema)
    directory = Path("logs")
    directory.mkdir(exist_ok=True)
    path = (
        directory
        / f"phase3-before-migration-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
    )
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(
            {"saved_at": datetime.now(UTC).isoformat(), "tables": before},
            stream,
            ensure_ascii=False,
        )
    config = Config("alembic.ini")
    config.attributes["connection"] = connection
    config.attributes["version_table_schema"] = schema
    command.upgrade(config, "0004_phase3")
    after = read_tables(connection, names, schema)
    for name in names:
        if name == "alembic_version":
            continue
        rows = []
        for original in after[name]:
            row = dict(original)
            if name == "chapters" and row.pop("planning_revision") != 0:
                raise RuntimeError(
                    "Unexpected initial planning revision; rolling back."
                )
            if name == "chapter_turns" and row.pop("scene_id") is not None:
                raise RuntimeError("Unexpected scene assignment; rolling back.")
            rows.append(row)
        if canonical(rows) != canonical(before[name]):
            raise RuntimeError(
                f"Existing {name} data changed. Migration will roll back."
            )
    if after["alembic_version"] != [{"version_num": "0004_phase3"}]:
        raise RuntimeError("Migration revision mismatch; rolling back.")
    for table in ("chapter_plans", "scenes", "scene_characters"):
        if connection.scalar(
            text(f"SELECT count(*) FROM {quote(schema)}.{quote(table)}")
        ):
            raise RuntimeError("Unexpected planning records; rolling back.")
    print(f"Private pre-migration data snapshot: {path.resolve()}")
    print(
        f"Phase 3 applied. All {len(names) - 1} existing application tables preserved; planning revisions start at 0 and paragraph scene links at NULL."
    )


async def main():
    try:
        async with engine.begin() as connection:
            await connection.execute(text("SET LOCAL lock_timeout = '10s'"))
            await connection.run_sync(migrate)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
