import unittest
from unittest.mock import AsyncMock, Mock

from sqlalchemy.exc import DBAPIError

from app.core.schema import EXPECTED_SCHEMA_REVISION, check_schema_revision


class SchemaRevisionTests(unittest.IsolatedAsyncioTestCase):
    def connection(self, revisions):
        result = Mock()
        result.scalars.return_value.all.return_value = revisions
        return Mock(execute=AsyncMock(return_value=result))

    async def test_current_revision_passes_without_migration_files(self):
        await check_schema_revision(self.connection([EXPECTED_SCHEMA_REVISION]))

    async def test_missing_old_new_and_multiple_revisions_fail(self):
        for revisions in ([], ["0004_phase3"], ["0006_future"],
                          [EXPECTED_SCHEMA_REVISION, "other_head"]):
            with self.subTest(revisions=revisions):
                with self.assertRaisesRegex(RuntimeError, "revision mismatch"):
                    await check_schema_revision(self.connection(revisions))

    async def test_missing_version_table_explains_recovery(self):
        original = Exception("undefined table")
        original.sqlstate = "42P01"
        connection = Mock(execute=AsyncMock(side_effect=DBAPIError(
            "SELECT version_num FROM alembic_version", {}, original
        )))
        with self.assertRaisesRegex(RuntimeError, "alembic_version is missing"):
            await check_schema_revision(connection)

    async def test_other_database_errors_are_preserved(self):
        error = DBAPIError("SELECT version_num FROM alembic_version", {},
                           Exception("connection unavailable"))
        connection = Mock(execute=AsyncMock(side_effect=error))
        with self.assertRaises(DBAPIError) as raised:
            await check_schema_revision(connection)
        self.assertIs(raised.exception, error)


if __name__ == "__main__":
    unittest.main()
