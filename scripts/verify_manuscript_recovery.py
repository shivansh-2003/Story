"""Read-only recovery verification and private application-data snapshot.

Run with PYTHONPATH=. venv/bin/python scripts/verify_manuscript_recovery.py.
STORY_RECOVERY_DATABASE_URL optionally selects a historical recovery branch.
This script never writes to PostgreSQL. The JSON snapshot is data, not a schema dump.
"""

import asyncio
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import get_settings


async def main():
    settings = get_settings()
    engine = create_async_engine(
        os.environ.get("STORY_RECOVERY_DATABASE_URL", settings.database_url),
        connect_args={"ssl": "require"} if settings.database_ssl_require else {},
    )
    original = json.loads(
        Path("logs/phase1-before-migration-20261010T125252804004Z.json").read_text()
    )
    expected = {str(row["id"]): row["content"] for row in original["turns"]}
    try:
        async with engine.connect() as connection:
            async with connection.begin():
                await connection.execute(
                    text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
                )
                names = (
                    (
                        await connection.execute(
                            text(
                                "SELECT tablename FROM pg_tables "
                                "WHERE schemaname = 'public' ORDER BY tablename"
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                tables = {}
                quote = connection.dialect.identifier_preparer.quote_identifier
                for name in names:
                    raw = await connection.scalar(
                        text(
                            "SELECT COALESCE(json_agg(row_to_json(t)), '[]'::json)::text "
                            f"FROM public.{quote(name)} AS t"
                        )
                    )
                    tables[name] = json.loads(raw)
                actual = {
                    row["id"]: row["content"] for row in tables.get("chapter_turns", [])
                }
                matches = all(
                    actual.get(key) == value for key, value in expected.items()
                )
                if not matches:
                    raise RuntimeError(
                        "Original paragraph IDs/content are missing or changed. "
                        "Recovery is not verified; no snapshot written."
                    )
                missing_history = await connection.scalar(
                    text(
                        "SELECT count(*) FROM public.chapter_turns AS t "
                        "WHERE NOT EXISTS (SELECT 1 FROM public.turn_revisions AS r "
                        "WHERE r.turn_id=t.id AND r.revision_number=t.version "
                        "AND r.content=t.content)"
                    )
                )
                version = tables.get("alembic_version", [])
                if version not in ([{"version_num": "0002_phase1"}], [{"version_num": "0003_phase2"}], [{"version_num": "0004_phase3"}], [{"version_num": "0005_phase4"}]) or missing_history:
                    raise RuntimeError(
                        "Manuscript schema/current revision history is incomplete."
                    )
        directory = Path("logs")
        directory.mkdir(exist_ok=True)
        path = directory / (
            "phase1-recovered-data-"
            + datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")
            + ".json"
        )
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w") as stream:
            json.dump(
                {"saved_at": datetime.now(UTC).isoformat(), "tables": tables},
                stream,
                ensure_ascii=False,
            )
        print(
            json.dumps(
                {
                    "original_paragraphs_verified": len(expected),
                    "missing_current_history": missing_history,
                    "counts": {name: len(rows) for name, rows in tables.items()},
                    "private_data_snapshot": str(path.resolve()),
                }
            )
        )
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
