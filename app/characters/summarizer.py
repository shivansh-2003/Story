import uuid
import hashlib
import json

from sqlalchemy import update

from app.characters.models import Character
from app.core.llm_client import call_model
from app.core.logging_utils import log_execution
from app.database import async_session
from app.jobs.models import BackgroundJob

CONDENSE_MAX_TOKENS = 80

# Every field consumed by the summary prompt must invalidate its result.
_SUMMARY_INPUT_FIELDS = (
    "name",
    "role",
    "appearance",
    "voice_notes",
    "personality_traits",
    "motivation",
    "flaw",
    "backstory",
)


def summary_source(character: Character) -> dict:
    return {field: getattr(character, field) for field in _SUMMARY_INPUT_FIELDS}


def source_revision(source: dict) -> int:
    # Fits the existing job revision INTEGER without a schema change. The
    # final write compares every source field, not just this scheduling token.
    digest = hashlib.sha256(json.dumps(source, sort_keys=True).encode()).digest()
    return int.from_bytes(digest[:4], "big") & 0x7FFFFFFF


def schedule_summary(db, character: Character) -> None:
    character.condensed_summary = None
    db.add(BackgroundJob(
        kind="character_summary", target_id=character.id,
        target_revision=source_revision(summary_source(character)),
    ))


def _build_prompt(character: Character) -> str:
    traits = ", ".join(character.personality_traits) if character.personality_traits else None
    fields = {
        "Name": character.name,
        "Role": character.role,
        "Appearance": character.appearance,
        "Voice notes": character.voice_notes,
        "Personality traits": traits,
        "Motivation": character.motivation,
        "Flaw": character.flaw,
        "Backstory": character.backstory,
    }
    lines = [f"{label}: {value}" for label, value in fields.items() if value]
    sheet = "\n".join(lines)
    return (
        "Compress this character sheet into 1-2 dense sentences suitable for "
        "inclusion in an AI writing assistant's system prompt. Capture voice, "
        "core personality, and defining motivation or flaw — not a biography. "
        "Write in third person, present tense, no preamble.\n\n"
        f"{sheet}"
    )


def should_resummarize(changed_fields: set[str]) -> bool:
    """True if any field that actually feeds the condensed summary changed —
    avoids a model call on a trivial PATCH (e.g. pronouns, age)."""
    return bool(changed_fields & set(_SUMMARY_INPUT_FIELDS))


@log_execution
async def summarize_character(character_id: uuid.UUID, expected_revision: int) -> bool:
    """Read a source snapshot, infer without a DB connection, then compare-and-save."""
    async with async_session() as db:
        character = await db.get(Character, character_id)
        if character is None or character.is_archived:
            return False
        source = summary_source(character)
        if source_revision(source) != expected_revision:
            return False
        prompt = _build_prompt(character)
    summary = (await call_model(prompt, max_tokens=CONDENSE_MAX_TOKENS)).strip()
    if not summary:
        raise ValueError("Empty character summary")
    async with async_session() as db:
        result = await db.execute(
            update(Character).where(
                Character.id == character_id,
                Character.is_archived.is_(False),
                *(getattr(Character, field).is_not_distinct_from(value)
                  for field, value in source.items()),
            ).values(condensed_summary=summary)
        )
        await db.commit()
        return result.rowcount == 1
