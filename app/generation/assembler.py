import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.service import list_active_characters
from app.characters.models import Character, CharacterRelationship
from app.characters.service import list_relationships_among
from app.stories.models import Story

MAX_PROMPT_TOKENS = 6000  # tune against your model; leaves room for generation output


async def build_continue_prompt(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    story_id: uuid.UUID,
    session_state: dict,
    prior_chapter_summaries: list[str],
    instruction: str,
    length_words: int,
) -> str:
    """Used for: fresh generate, and regenerate-after-AI-draft (when pending_turn
    either doesn't exist or was AI-sourced, not user-edited)."""
    story = await db.get(Story, story_id)
    characters = await list_active_characters(db, chapter_id)
    relationships = await list_relationships_among(db, [c.id for c in characters])

    parts = [_format_bible(story), _format_characters(characters)]
    relationships_text = _format_relationships(characters, relationships)
    if relationships_text:
        parts.append(relationships_text)
    if prior_chapter_summaries:
        parts.append(_format_prior_summaries(prior_chapter_summaries))
    if session_state["running_summary"]:
        parts.append(f"Chapter so far (summary): {session_state['running_summary']}")

    raw_tail = session_state["raw_tail"][-2:]  # last 1-2 paragraphs, always verbatim
    if raw_tail:
        parts.append("Most recent text (write in this exact voice):\n" + "\n\n".join(raw_tail))

    parts.append(f"Instruction: {instruction}")
    parts.append(f"Write approximately {length_words} words. Continue directly — no preamble.")

    return _enforce_budget("\n\n".join(parts))


async def build_edit_prompt(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    story_id: uuid.UUID,
    session_state: dict,
    instruction: str,
) -> str:
    """Used for: edit-in-place, and regenerate-after-user-edit.
    Deliberately does NOT include raw_tail or prior chapter summaries —
    editing should act on the pending draft only, not pull in the whole
    chapter's context and risk rewriting more than intended."""
    story = await db.get(Story, story_id)
    characters = await list_active_characters(db, chapter_id)
    relationships = await list_relationships_among(db, [c.id for c in characters])
    pending = session_state["pending_turn"]
    if pending is None:
        raise ValueError("No pending turn to edit")

    parts = [_format_bible(story), _format_characters(characters)]
    relationships_text = _format_relationships(characters, relationships)
    if relationships_text:
        parts.append(relationships_text)
    parts += [
        f"Current draft text:\n{pending['content']}",
        f"Edit instruction: {instruction}",
        "Return only the revised paragraph(s), same approximate length.",
    ]
    return _enforce_budget("\n\n".join(parts))


def _enforce_budget(prompt: str) -> str:
    # ponytail: word-count proxy for tokens, not a real tokenizer count.
    # Swap for a real token counter if trimming starts mattering.
    approx_tokens = len(prompt.split()) * 1.3
    if approx_tokens <= MAX_PROMPT_TOKENS:
        return prompt
    # simplest correct approach — truncate from the front, keep instruction + tail
    words = prompt.split()
    keep = int(MAX_PROMPT_TOKENS / 1.3)
    return " ".join(words[-keep:])


def _format_bible(story: Story) -> str:
    # skip unset fields rather than printing "Tone: None" into the prompt —
    # most of these are optional and a writer may never fill them in.
    fields = {
        "Genre": ", ".join(story.genre) if story.genre else None,
        "Tone": story.tone,
        "POV": story.pov,
        "Tense": story.tense,
        "Setting": story.setting,
        "Themes": ", ".join(story.themes) if story.themes else None,
        "Premise": story.premise,
        "Content boundaries": story.content_boundaries,
        "Writing style": story.writing_style_notes,
        "Target audience": story.target_audience,
    }
    lines = [f"{label}: {value}" for label, value in fields.items() if value]
    return f"Story: {story.title}\n" + "\n".join(lines)


def _format_characters(characters: list[Character]) -> str:
    lines = []
    for c in characters:
        line = f"- {c.name}"
        if c.role:
            line += f" ({c.role})"
        if c.condensed_summary:
            line += f": {c.condensed_summary}"
        lines.append(line)
    return "Characters in scene:\n" + "\n".join(lines)


def _format_relationships(
    characters: list[Character], relationships: list[CharacterRelationship]
) -> str | None:
    if not relationships:
        return None
    names = {c.id: c.name for c in characters}
    lines = [
        f"- {names[r.character_id]} → {names[r.related_character_id]}: {r.relationship_label or 'connected'}"
        for r in relationships
    ]
    return "Relationships:\n" + "\n".join(lines)


def _format_prior_summaries(summaries: list[str]) -> str:
    return "Story so far:\n" + "\n".join(f"- {s}" for s in summaries)


def _demo() -> None:
    short = "one two three"
    assert _enforce_budget(short) == short

    long_prompt = " ".join(str(i) for i in range(10_000))
    trimmed = _enforce_budget(long_prompt)
    assert trimmed != long_prompt
    assert trimmed.endswith("9999")
    assert len(trimmed.split()) * 1.3 <= MAX_PROMPT_TOKENS + 1
    print("assembler self-check passed")


if __name__ == "__main__":
    _demo()
