import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.service import list_active_characters
from app.characters.models import Character, CharacterRelationship
from app.characters.service import list_relationships_among
from app.stories.models import Story

MAX_PROMPT_TOKENS = 6000  # applies to the user message only — see _assemble_continue_user


async def build_continue_prompt(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    story_id: uuid.UUID,
    session_state: dict,
    prior_chapter_summaries: list[str],
    instruction: str,
    length_words: int,
) -> tuple[str, str]:
    """Used for: fresh generate, and regenerate-after-AI-draft (when pending_turn
    either doesn't exist or was AI-sourced, not user-edited).

    Returns (system, user). `system` — bible + characters + relationships — is
    identical across every regenerate/edit within a chapter, so keeping it in
    its own message lets a provider (or Ollama's own KV-cache) reuse that
    prefix across a generate → regenerate → edit burst instead of re-sending
    and re-evaluating it fresh every call."""
    story = await db.get(Story, story_id)
    characters = await list_active_characters(db, chapter_id)
    relationships = await list_relationships_among(db, [c.id for c in characters])

    system = _build_system_prompt(story, characters, relationships)
    user = _assemble_continue_user(
        prior_summaries=prior_chapter_summaries,
        running_summary=session_state["running_summary"],
        raw_tail=session_state["raw_tail"][-2:],  # last 1-2 paragraphs, always verbatim
        instruction=instruction,
        length_words=length_words,
    )
    return system, user


async def build_edit_prompt(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    story_id: uuid.UUID,
    session_state: dict,
    instruction: str,
) -> tuple[str, str]:
    """Used for: edit-in-place, and regenerate-after-user-edit.
    Deliberately does NOT include raw_tail or prior chapter summaries —
    editing should act on the pending draft only, not pull in the whole
    chapter's context and risk rewriting more than intended.

    No trimming applied here: the draft + edit instruction are exactly the
    "never trim" content per _assemble_continue_user's ladder, so there's
    nothing left that budget enforcement would ever touch."""
    story = await db.get(Story, story_id)
    characters = await list_active_characters(db, chapter_id)
    relationships = await list_relationships_among(db, [c.id for c in characters])
    pending = session_state["pending_turn"]
    if pending is None:
        raise ValueError("No pending turn to edit")

    system = _build_system_prompt(story, characters, relationships)
    user = "\n\n".join(
        [
            f"Current draft text:\n{pending['content']}",
            f"Edit instruction: {instruction}",
            "Return only the revised paragraph(s), same approximate length.",
        ]
    )
    return system, user


def _build_system_prompt(
    story: Story, characters: list[Character], relationships: list[CharacterRelationship]
) -> str:
    parts = [_format_bible(story), _format_characters(characters)]
    relationships_text = _format_relationships(characters, relationships)
    if relationships_text:
        parts.append(relationships_text)
    return "\n\n".join(parts)


def _assemble_continue_user(
    prior_summaries: list[str],
    running_summary: str,
    raw_tail: list[str],
    instruction: str,
    length_words: int,
) -> str:
    """Priority-ordered budget enforcement, cheapest-to-lose first:
    1. oldest prior-chapter summaries, one at a time
    2. the running summary, wholesale (it's already a 2-4 sentence rollup —
       no finer-grained truncation is worth building for that little text)
    3. the older of the two raw_tail paragraphs
    Never trimmed: the instruction and length directive — sent even if the
    prompt is still over budget after exhausting 1-3, since a truncated
    instruction is worse than a long prompt."""
    summaries = list(prior_summaries)  # oldest first, per get_prior_chapter_summaries' ordering
    tail = list(raw_tail)
    summary = running_summary

    protected = [
        f"Instruction: {instruction}",
        f"Write approximately {length_words} words. Continue directly — no preamble.",
    ]

    def render() -> str:
        parts = []
        if summaries:
            parts.append(_format_prior_summaries(summaries))
        if summary:
            parts.append(f"Chapter so far (summary): {summary}")
        if tail:
            parts.append("Most recent text (write in this exact voice):\n" + "\n\n".join(tail))
        return "\n\n".join(parts + protected)

    prompt = render()
    while _approx_tokens(prompt) > MAX_PROMPT_TOKENS and summaries:
        summaries.pop(0)
        prompt = render()
    while _approx_tokens(prompt) > MAX_PROMPT_TOKENS and summary:
        summary = ""
        prompt = render()
    while _approx_tokens(prompt) > MAX_PROMPT_TOKENS and len(tail) > 1:
        tail.pop(0)
        prompt = render()
    return prompt


def _approx_tokens(text: str) -> float:
    # ponytail: word-count proxy for tokens, not a real tokenizer count.
    # Swap for a real token counter if trimming starts mattering.
    return len(text.split()) * 1.3


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
    huge_summaries = [f"chapter {i} summary text goes here" for i in range(2000)]
    prompt = _assemble_continue_user(
        prior_summaries=huge_summaries,
        running_summary="running summary text",
        raw_tail=["paragraph one", "paragraph two"],
        instruction="write the next scene",
        length_words=100,
    )
    assert "Instruction: write the next scene" in prompt  # never trimmed
    assert "Write approximately 100 words" in prompt  # never trimmed
    assert "chapter 0 summary" not in prompt  # oldest dropped first
    assert "chapter 1999 summary" in prompt  # most recent summary kept longest

    small = _assemble_continue_user(
        prior_summaries=["a short summary"],
        running_summary="",
        raw_tail=[],
        instruction="continue",
        length_words=50,
    )
    assert "a short summary" in small  # nothing dropped when comfortably under budget

    print("assembler self-check passed")


if __name__ == "__main__":
    _demo()
