"""Add rewrite proposals with a private snapshot and unchanged-row verification."""

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from alembic.config import Config
from sqlalchemy import inspect, text

from alembic import command
from app.database import engine
from scripts.migrate_manuscript_imports import canonical, read_tables


def migrate(connection):
    schema = connection.scalar(text("SELECT current_schema()"))
    quote = connection.dialect.identifier_preparer.quote_identifier
    revision = connection.scalar(
        text(f"SELECT version_num FROM {quote(schema)}.alembic_version")
    )
    if revision == "0005_phase4":
        print("AI rewrites migration is already applied.")
        return
    if revision != "0004_phase3":
        raise RuntimeError("Scene planning must be migrated first. No changes applied.")
    names = sorted(inspect(connection).get_table_names(schema=schema))
    if "rewrite_proposals" in names:
        raise RuntimeError(
            "Unexpected rewrite table already exists. Inspect schema drift first."
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
        / f"phase4-before-migration-{datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ')}.json"
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
    command.upgrade(config, "0005_phase4")
    after = read_tables(connection, names, schema)
    for name in names:
        if name != "alembic_version" and canonical(after[name]) != canonical(
            before[name]
        ):
            raise RuntimeError(
                f"Existing {name} data changed. Migration will roll back."
            )
    if after["alembic_version"] != [{"version_num": "0005_phase4"}]:
        raise RuntimeError("Migration revision mismatch; rolling back.")
    if connection.scalar(
        text(f"SELECT count(*) FROM {quote(schema)}.rewrite_proposals")
    ):
        raise RuntimeError("Unexpected rewrite proposals; rolling back.")
    print(f"Private pre-migration data snapshot: {path.resolve()}")
    print(
        f"AI rewrites migration applied. All {len(names) - 1} existing application tables preserved."
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
