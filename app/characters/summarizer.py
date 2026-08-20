import uuid

from app.characters.models import Character
from app.core.llm_client import call_model
from app.core.logging_utils import log_execution
from app.database import async_session

CONDENSE_MAX_TOKENS = 80

# Fields that actually feed the condensed summary — used both to build the
# prompt and to decide whether an update needs to re-trigger summarization.
# Excludes id, user_id, name, role, age, pronouns, is_archived, timestamps —
# name/role are still included in the prompt text for grounding, but
# changing them alone doesn't change who the character IS.
_SUMMARY_INPUT_FIELDS = (
    "appearance",
    "voice_notes",
    "personality_traits",
    "motivation",
    "flaw",
    "backstory",
)


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
async def summarize_character(character_id: uuid.UUID) -> None:
    """Background job — re-fetches the character fresh since this runs after
    the request's own db session has already closed."""
    async with async_session() as db:
        character = await db.get(Character, character_id)
        if character is None:
            return  # archived/deleted between scheduling and running — nothing to do

        prompt = _build_prompt(character)
        summary = await call_model(prompt, max_tokens=CONDENSE_MAX_TOKENS)

        character.condensed_summary = summary.strip()
        await db.commit()
