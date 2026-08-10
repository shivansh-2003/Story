import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.service import list_active_characters
from app.characters.models import Character
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

    parts = [_format_bible(story), _format_characters(characters)]
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
    pending = session_state["pending_turn"]
    if pending is None:
        raise ValueError("No pending turn to edit")

    parts = [
        _format_bible(story),
        _format_characters(characters),
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
    return (
        f"Story: {story.title} | Genre: {story.genre} | Tone: {story.tone} | "
        f"POV: {story.pov} | Premise: {story.premise}"
    )


def _format_characters(characters: list[Character]) -> str:
    return "Characters in scene:\n" + "\n".join(
        f"- {c.name} ({c.role}): {c.condensed_summary}" for c in characters
    )


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
