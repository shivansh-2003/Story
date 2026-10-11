"""Apply the additive Phase 2 migration, verifying all existing table data.

Run: PYTHONPATH=. venv/bin/python scripts/migrate_phase2.py
Takes a private data snapshot under ignored logs/ and rolls back if existing
records change. This is a data snapshot, not a complete schema backup.
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


def read_tables(connection, names, schema):
    quote = connection.dialect.identifier_preparer.quote_identifier
    return {
        name: json.loads(
            connection.scalar(
                text(
                    "SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json)::text "
                    f"FROM {quote(schema)}.{quote(name)} AS t"
                )
            )
        )
        for name in names
    }


def canonical(rows):
    return sorted(json.dumps(row, sort_keys=True, ensure_ascii=False) for row in rows)


def migrate(connection):
    schema = connection.scalar(text("SELECT current_schema()"))
    quote = connection.dialect.identifier_preparer.quote_identifier
    revision = connection.scalar(
        text(f"SELECT version_num FROM {quote(schema)}.alembic_version")
    )
    if revision in {"0003_phase2", "0004_phase3", "0005_phase4"}:
        print("Phase 2 is already applied.")
        return
    if revision != "0002_phase1":
        raise RuntimeError("Phase 1 must be migrated first. No changes applied.")
    names = sorted(inspect(connection).get_table_names(schema=schema))
    if "import_previews" in names:
        raise RuntimeError(
            "Unexpected import table already exists. Inspect schema drift first."
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
        / f"phase2-before-migration-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
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
    command.upgrade(config, "0003_phase2")
    after = read_tables(connection, names, schema)
    for name in names:
        if name != "alembic_version" and canonical(before[name]) != canonical(
            after[name]
        ):
            raise RuntimeError(
                f"Existing {name} data changed. Migration will roll back."
            )
    if after["alembic_version"] != [{"version_num": "0003_phase2"}]:
        raise RuntimeError("Migration revision mismatch. Migration will roll back.")
    print(f"Private pre-migration data snapshot: {path.resolve()}")
    print(
        f"Phase 2 applied. All {len(names) - 1} existing application tables are unchanged."
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
