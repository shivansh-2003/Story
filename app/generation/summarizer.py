import uuid

from app.chapters.service import get_chapter_body, update_chapter_summary
from app.core.llm_client import call_model
from app.database import async_session
from app.generation import session_store

COMPACTION_WORD_THRESHOLD = 700


async def maybe_compact_session(chapter_id: uuid.UUID) -> None:
    """Trigger 1 — intra-chapter, length-based.
    Called from the accept endpoint AFTER saving the session, fire-and-forget
    via BackgroundTasks. Idempotent-ish: re-checks the counter itself, so it's
    safe if called slightly more than strictly necessary."""
    state = await session_store.get_session(chapter_id)
    if state["word_count_since_compaction"] < COMPACTION_WORD_THRESHOLD:
        return

    # everything except the last 1-2 paragraphs (which stay as raw_tail) gets folded in
    to_compact = state["raw_tail"][:-2] if len(state["raw_tail"]) > 2 else []
    if not to_compact:
        # nothing new to fold in — calling the model here would just pay for a
        # paraphrase of the existing summary (and risk it drifting) for no reason.
        return

    prompt = (
        f"Existing summary: {state['running_summary'] or '(none yet)'}\n"
        f"New text to fold in:\n" + "\n\n".join(to_compact) + "\n\n"
        "Write an updated running summary of this chapter so far, 2-4 sentences, "
        "preserving key events and character state changes."
    )
    new_summary = await call_model(prompt, max_tokens=150)

    state["running_summary"] = new_summary
    state["raw_tail"] = state["raw_tail"][-2:]
    state["word_count_since_compaction"] = 0
    await session_store.save_session(chapter_id, state)

    async with async_session() as db:
        await update_chapter_summary(db, chapter_id, running_summary_cache=new_summary)


async def summarize_completed_chapter(chapter_id: uuid.UUID) -> None:
    """Trigger 2 — inter-chapter, event-based.
    Called on chapter status -> complete, AND on any edit to an already-complete
    chapter's text (same trigger condition, not a special case)."""
    state = await session_store.get_session(chapter_id)

    full_text = state["running_summary"]
    if state["raw_tail"]:
        full_text += "\n\n" + "\n\n".join(state["raw_tail"])

    async with async_session() as db:
        if not full_text.strip():
            # session already cleared (e.g. re-summarize path) — fall back to durable turns
            full_text = await get_chapter_body(db, chapter_id)

        prompt = (
            "Summarize this chapter in 2-4 sentences for use as context in future "
            "chapters. Focus on plot events, character decisions, and unresolved threads.\n\n"
            f"{full_text}"
        )
        summary = await call_model(prompt, max_tokens=150)
        await update_chapter_summary(db, chapter_id, chapter_summary=summary)

    await session_store.clear_session(chapter_id)
