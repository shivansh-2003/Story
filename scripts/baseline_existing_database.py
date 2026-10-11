"""Verify the pre-phase-1 schema before optionally stamping its Alembic baseline.

Read-only by default. Stop the backend before running with --stamp and upgrading.
"""

import argparse
import asyncio

from alembic.config import Config
from sqlalchemy import ARRAY, String, inspect, text

import app.main  # noqa: F401 -- register all models
from alembic import command
from app.database import Base, engine

NEW_TABLES = {"turn_revisions", "background_jobs"}
NEW_COLUMNS = {
    "chapter_turns": {
        "version",
        "source",
        "updated_at",
        "accepted_draft_id",
        "embedding_version",
    },
    "chapters": {"manuscript_revision", "memory_revision"},
}


def equivalent_type(expected, actual, dialect):
    if isinstance(expected, ARRAY) and isinstance(actual, ARRAY):
        return equivalent_type(expected.item_type, actual.item_type, dialect)
    # Older installations use TEXT[] for fields now modeled as unbounded VARCHAR[].
    # Both preserve arbitrary strings without truncation.
    if (
        isinstance(expected, String)
        and isinstance(actual, String)
        and expected.length is None
        and actual.length is None
        and not getattr(expected, "enums", None)
        and not getattr(actual, "enums", None)
    ):
        return True
    return str(expected.compile(dialect=dialect)) == str(
        actual.compile(dialect=dialect)
    )


def verify(connection):
    inspector = inspect(connection)
    names = set(inspector.get_table_names())
    if "alembic_version" in names:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        if revision:
            raise RuntimeError(
                "Database already has an Alembic revision; use alembic upgrade head."
            )
    for table in Base.metadata.sorted_tables:
        if table.name in NEW_TABLES:
            if table.name not in names:
                continue
            # Older create_all startup may have created these before upgrading old columns.
            # Accept only matching, empty tables; never discard existing history or jobs.
            if connection.scalar(text(f"SELECT count(*) FROM {table.name}")):
                raise RuntimeError(
                    f"Unversioned phase-1 table contains data: {table.name}"
                )
        if table.name not in names:
            raise RuntimeError(f"Missing baseline table: {table.name}")
        expected = {
            col.name: col
            for col in table.columns
            if col.name not in NEW_COLUMNS.get(table.name, set())
        }
        existing = {col["name"]: col for col in inspector.get_columns(table.name)}
        if set(existing) != set(expected):
            raise RuntimeError(f"Columns differ from baseline: {table.name}")
        for name, column in expected.items():
            actual = existing[name]
            if column.nullable != actual["nullable"]:
                raise RuntimeError(f"Nullability differs: {table.name}.{name}")
            # SQLAlchemy may not recognize pgvector until its extension type is registered.
            if name != "embedding" and not equivalent_type(
                column.type, actual["type"], connection.dialect
            ):
                raise RuntimeError(f"Type differs: {table.name}.{name}")
        expected_pk = {col.name for col in table.primary_key.columns}
        if (
            set(inspector.get_pk_constraint(table.name)["constrained_columns"])
            != expected_pk
        ):
            raise RuntimeError(f"Primary key differs: {table.name}")
        actual_fks = {
            (
                tuple(fk["constrained_columns"]),
                fk["referred_table"],
                tuple(fk["referred_columns"]),
            )
            for fk in inspector.get_foreign_keys(table.name)
        }
        for constraint in table.foreign_key_constraints:
            signature = (
                tuple(col.name for col in constraint.columns),
                constraint.referred_table.name,
                tuple(element.column.name for element in constraint.elements),
            )
            if signature not in actual_fks:
                raise RuntimeError(f"Foreign key differs: {table.name}")
        actual_uniques = {
            tuple(c["column_names"])
            for c in inspector.get_unique_constraints(table.name)
        }
        actual_uniques |= {
            tuple(i["column_names"])
            for i in inspector.get_indexes(table.name)
            if i["unique"]
        }
        from sqlalchemy import UniqueConstraint

        for constraint in table.constraints:
            if (
                isinstance(constraint, UniqueConstraint)
                and constraint.name != "uq_turn_sequence"
                and not any(
                    col.name in NEW_COLUMNS.get(table.name, set())
                    for col in constraint.columns
                )
            ):
                if tuple(col.name for col in constraint.columns) not in actual_uniques:
                    raise RuntimeError(f"Unique constraint differs: {table.name}")
    duplicate = connection.execute(
        text(
            "SELECT chapter_id FROM chapter_turns GROUP BY chapter_id, sequence HAVING count(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicate:
        raise RuntimeError(
            "Duplicate paragraph sequences exist; resolve them before migration."
        )
    # Enum labels matter even when the reflected type name matches.
    enums = {enum["name"]: set(enum["labels"]) for enum in inspector.get_enums()}
    from sqlalchemy import Enum

    for table in Base.metadata.tables.values():
        for col in table.columns:
            if isinstance(col.type, Enum) and set(col.type.enums) != enums.get(
                col.type.name
            ):
                raise RuntimeError(
                    f"Enum values differ: {col.type.name}; apply legacy schema migrations first."
                )


async def check():
    async with engine.connect() as connection:
        await connection.run_sync(verify)
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stamp",
        action="store_true",
        help="Stamp the verified pre-phase-1 baseline; does not add phase-1 tables.",
    )
    args = parser.parse_args()
    asyncio.run(check())
    print("Existing schema matches the pre-phase-1 baseline.")
    if args.stamp:
        command.stamp(Config("alembic.ini"), "0001_baseline")
        print("Baseline stamped. Run alembic upgrade head next.")
