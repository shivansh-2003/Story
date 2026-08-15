"""One-off schema migration for the backend/LLM-workflow optimization pass.

No Alembic in this project — Base.metadata.create_all() on startup only
creates missing tables, it never alters existing ones. This script applies
the two changes that need an ALTER against the live database:

  - new indexes on hot foreign-key columns (chapter_turns.chapter_id,
    character_relationships.character_id/related_character_id,
    characters.user_id, stories.user_id, chapters.story_id)
  - new enum values (StoryStatus.on_hold, ChapterStatus.in_review/locked)

Idempotent — every statement uses IF NOT EXISTS, safe to run more than once.
Uses AUTOCOMMIT so each ALTER TYPE ... ADD VALUE takes effect immediately
(a value added inside an explicit transaction can't be used in that same
transaction on some PG versions — sidestep the edge case entirely).

Run BEFORE restarting the app with the new enum members, or inserts using
the new values will fail against the old Postgres enum type.
"""

import asyncio

from sqlalchemy import text

from app.database import engine

INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS ix_chapter_turns_chapter_id ON chapter_turns (chapter_id)",
    "CREATE INDEX IF NOT EXISTS ix_character_relationships_character_id ON character_relationships (character_id)",
    "CREATE INDEX IF NOT EXISTS ix_character_relationships_related_character_id "
    "ON character_relationships (related_character_id)",
    "CREATE INDEX IF NOT EXISTS ix_characters_user_id ON characters (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_stories_user_id ON stories (user_id)",
    "CREATE INDEX IF NOT EXISTS ix_chapters_story_id ON chapters (story_id)",
]

ENUM_STATEMENTS = [
    "ALTER TYPE story_status ADD VALUE IF NOT EXISTS 'on_hold'",
    "ALTER TYPE chapter_status ADD VALUE IF NOT EXISTS 'in_review'",
    "ALTER TYPE chapter_status ADD VALUE IF NOT EXISTS 'locked'",
]


async def migrate() -> None:
    async with engine.connect() as conn:
        autocommit_conn = await conn.execution_options(isolation_level="AUTOCOMMIT")
        for stmt in INDEX_STATEMENTS + ENUM_STATEMENTS:
            print(f"-> {stmt}")
            await autocommit_conn.execute(text(stmt))
    print("migration complete")


if __name__ == "__main__":
    asyncio.run(migrate())
