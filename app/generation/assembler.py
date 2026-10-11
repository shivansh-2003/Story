import asyncio
import uuid

from app.chapters.service import get_prior_chapter_summaries
from app.characters.models import Character, CharacterRelationship
from app.characters.queries import chapter_cast, cast_relationships
from app.core.logging_utils import log_execution
from app.database import async_session
from app.generation import semantic_search
from app.manuscript.memory import accepted_context
from app.stories.models import Story

MAX_PROMPT_TOKENS = 6000  # applies to the user message only — see _assemble_continue_user
MAX_RETRIEVED_TURNS_CHARS = 1500  # ceiling so one very long retrieved paragraph can't dominate


async def _prompt_sources(chapter_id, story_id, planning_context, *, include_memory):
    # Serialize these short reads on one session; do not fan out one database
    # connection per feature or interleave AsyncSession operations.
    async with async_session() as db:
        story = await db.get(Story, story_id)
        characters = planning_context["characters"]
        if characters is None:
            characters = await chapter_cast(db, chapter_id)
        relationships = await cast_relationships(db, [c.id for c in characters])
        summaries = await get_prior_chapter_summaries(db, story_id, chapter_id) if include_memory else []
        context = await accepted_context(chapter_id, db) if include_memory else None
    return story, characters, relationships, summaries, context


@log_execution
async def _fetch_relevant_turns(story_id: uuid.UUID, chapter_id: uuid.UUID, instruction: str) -> list[str]:
    """Independent of the other source reads — only needs the
    instruction text, already available as a function parameter. Returns []
    on any embedding failure (rate limit, timeout) rather than raising —
    retrieval is an enhancement, not a hard requirement for generation to
    proceed."""
    try:
        query_vector = await semantic_search.embed_query(instruction)
    except Exception:
        return []
    async with async_session() as db:
        turns = await semantic_search.search_relevant_turns(db, story_id, chapter_id, query_vector)
    return [t.content[:MAX_RETRIEVED_TURNS_CHARS] for t in turns]


async def build_continue_prompt(
    chapter_id: uuid.UUID,
    story_id: uuid.UUID,
    session_state: dict,
    instruction: str,
    length_words: int,
    planning_context: dict | None = None,
) -> tuple[str, str]:
    """Build continuation context with one source-read connection.

    Semantic retrieval runs concurrently, opening its own short read session
    only after embedding completes. No shared session is used concurrently.
    """
    planning_context = planning_context or {"text": "", "characters": None}

    sources, relevant_turns = await asyncio.gather(
        _prompt_sources(chapter_id, story_id, planning_context, include_memory=True),
        _fetch_relevant_turns(story_id, chapter_id, instruction),
    )
    story, characters, relationships, prior_chapter_summaries, context = sources

    session_state["manuscript_revision"] = context["manuscript_revision"]

    system = _build_system_prompt(story, characters, relationships)
    if planning_context["text"]:
        system += "\n\nPlanning describes intended events, not established facts. Follow the writer's current instruction when it differs from the plan."
    user = _assemble_continue_user(
        prior_summaries=prior_chapter_summaries,
        running_summary=context["running_summary"],
        raw_tail=context["raw_tail"],
        relevant_turns=relevant_turns,
        instruction=instruction,
        length_words=length_words,
        planning_text=planning_context["text"],
    )
    return system, user


async def build_edit_prompt(
    chapter_id: uuid.UUID,
    story_id: uuid.UUID,
    session_state: dict,
    instruction: str,
    planning_context: dict | None = None,
) -> tuple[str, str]:
    """Used for: edit-in-place, and regenerate-after-user-edit.
    Deliberately does NOT include raw_tail or prior chapter summaries —
    editing should act on the pending draft only, not pull in the whole
    chapter's context and risk rewriting more than intended.

    No trimming applied here: the draft + edit instruction are exactly the
    "never trim" content per _assemble_continue_user's ladder, so there's
    nothing left that budget enforcement would ever touch.

    Source reads share one short-lived database session."""
    planning_context = planning_context or {"text": "", "characters": None}

    story, characters, relationships, _, _ = await _prompt_sources(
        chapter_id, story_id, planning_context, include_memory=False
    )
    pending = session_state["pending_turn"]
    if pending is None:
        raise ValueError("No pending turn to edit")

    system = _build_system_prompt(story, characters, relationships)
    if planning_context["text"]:
        system += "\n\nPlanning describes intended events, not established facts. Follow the writer's current edit instruction when it differs from the plan."
    user = "\n\n".join(
        [
            planning_context["text"],
            f"Current draft text:\n{pending['content']}",
            f"Edit instruction: {instruction}",
            "Return only the revised paragraph(s), same approximate length.",
        ]
    )
    return system, user


@log_execution
def _build_system_prompt(
    story: Story, characters: list[Character], relationships: list[CharacterRelationship]
) -> str:
    parts = [_format_bible(story), _format_characters(characters)]
    relationships_text = _format_relationships(characters, relationships)
    if relationships_text:
        parts.append(relationships_text)
    return "\n\n".join(parts)


@log_execution
def _assemble_continue_user(
    prior_summaries: list[str],
    running_summary: str,
    raw_tail: list[str],
    relevant_turns: list[str],
    instruction: str,
    length_words: int,
    planning_text: str = "",
) -> str:
    """Priority-ordered budget enforcement, cheapest-to-lose first:
    1. oldest prior-chapter summaries, one at a time
    2. retrieved semantically-relevant turns, wholesale (already capped at
       semantic_search.TOP_K — a bonus callback aid, not baseline continuity,
       so it goes before the things that actually shape voice/continuity)
    3. the running summary, wholesale (it's already a 2-4 sentence rollup —
       no finer-grained truncation is worth building for that little text)
    4. the older of the two raw_tail paragraphs
    Never trimmed: the instruction and length directive — sent even if the
    prompt is still over budget after exhausting 1-4, since a truncated
    instruction is worse than a long prompt."""
    summaries = list(prior_summaries)  # oldest first, per get_prior_chapter_summaries' ordering
    tail = list(raw_tail)
    summary = running_summary
    retrieved = list(relevant_turns)

    protected = [
        *([planning_text] if planning_text else []),
        f"Instruction: {instruction}",
        f"Write approximately {length_words} words. Continue directly — no preamble.",
    ]

    def render() -> str:
        parts = []
        if summaries:
            parts.append(_format_prior_summaries(summaries))
        if retrieved:
            parts.append(_format_retrieved_context(retrieved))
        if summary:
            parts.append(f"Chapter so far (summary): {summary}")
        if tail:
            parts.append("Most recent text (write in this exact voice):\n" + "\n\n".join(tail))
        return "\n\n".join(parts + protected)

    prompt = render()
    while _approx_tokens(prompt) > MAX_PROMPT_TOKENS and summaries:
        summaries.pop(0)
        prompt = render()
    while _approx_tokens(prompt) > MAX_PROMPT_TOKENS and retrieved:
        retrieved = []  # dropped as a whole block — already capped at TOP_K, no long tail to trim piecemeal
        prompt = render()
    while _approx_tokens(prompt) > MAX_PROMPT_TOKENS and summary:
        summary = ""
        prompt = render()
    while _approx_tokens(prompt) > MAX_PROMPT_TOKENS and len(tail) > 1:
        tail.pop(0)
        prompt = render()
    return prompt


def _format_retrieved_context(turns: list[str]) -> str:
    return "Relevant past scenes (may be from any earlier chapter):\n" + "\n\n---\n\n".join(turns)


def _approx_tokens(text: str) -> float:
    # ponytail: word-count proxy for tokens, not a real tokenizer count.
    # Swap for a real token counter if trimming starts mattering.
    return len(text.split()) * 1.3


# _approx_tokens and _format_prior_summaries deliberately NOT decorated: both
# run inside _assemble_continue_user's trim loop and can fire hundreds of
# times for one prompt (once per dropped summary) — @log_execution there
# would be log spam with no extra signal, since _assemble_continue_user
# itself already logs one START/DONE pair for the whole trimming pass.
@log_execution
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


@log_execution
def _format_characters(characters: list[Character]) -> str:
    lines = []
    for c in characters:
        line = f"- {c.name}"
        if c.role:
            line += f" ({c.role})"
        if c.condensed_summary:
            line += f": {c.condensed_summary}"
        else:
            # Fresh character facts remain available while the durable summary
            # job is pending or failed; never fall back to an outdated summary.
            facts = [c.appearance, c.voice_notes, c.motivation, c.flaw, c.backstory]
            if c.personality_traits:
                facts.insert(0, ", ".join(c.personality_traits))
            fallback = "; ".join(str(value)[:300] for value in facts if value)
            if fallback:
                line += ": " + fallback
        lines.append(line)
    return "Characters in scene:\n" + "\n".join(lines)


@log_execution
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
        relevant_turns=["a retrieved callback paragraph"],
        instruction="write the next scene",
        length_words=100,
    )
    assert "Instruction: write the next scene" in prompt  # never trimmed
    assert "Write approximately 100 words" in prompt  # never trimmed
    assert "chapter 0 summary" not in prompt  # oldest dropped first
    assert "chapter 1999 summary" in prompt  # most recent summary kept longest
    assert "a retrieved callback paragraph" in prompt  # kept when comfortably under budget

    small = _assemble_continue_user(
        prior_summaries=["a short summary"],
        running_summary="",
        raw_tail=[],
        relevant_turns=[],
        instruction="continue",
        length_words=50,
    )
    assert "a short summary" in small  # nothing dropped when comfortably under budget
    assert "Relevant past scenes" not in small  # section omitted when empty

    tight_retrieval = _assemble_continue_user(
        prior_summaries=[],
        running_summary="keep this summary",
        raw_tail=["keep this tail"],
        relevant_turns=["filler word " * 6000],  # forces retrieval to be dropped before summary/tail
        instruction="continue",
        length_words=50,
    )
    assert "keep this summary" in tight_retrieval  # summary survives, dropped after retrieval
    assert "keep this tail" in tight_retrieval  # tail survives too
    assert "Relevant past scenes" not in tight_retrieval  # retrieval was the one dropped

    print("assembler self-check passed")


if __name__ == "__main__":
    _demo()
