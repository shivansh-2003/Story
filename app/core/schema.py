"""Database schema required by this application release.

Keep this revision in sync with schema changes. Runtime checks deliberately
do not load Alembic scripts: serving the app does not perform migrations.
"""

from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

EXPECTED_SCHEMA_REVISION = "0005_phase4"


async def check_schema_revision(connection) -> None:
    try:
        revisions = (await connection.execute(text(
            "SELECT version_num FROM alembic_version"
        ))).scalars().all()
    except DBAPIError as error:
        if getattr(error.orig, "sqlstate", None) != "42P01":
            raise
        raise RuntimeError(
            "Database migrations required: alembic_version is missing. "
            "Restore alembic.ini and the alembic/ revision directory, then "
            "verify the existing schema before applying migrations."
        ) from error
    if revisions != [EXPECTED_SCHEMA_REVISION]:
        raise RuntimeError(
            f"Database schema revision mismatch: expected {EXPECTED_SCHEMA_REVISION}, "
            f"found {revisions!r}. Restore migration files if missing and run "
            "the appropriate reviewed migration before starting the server."
        )
