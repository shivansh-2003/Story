from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.core.errors import DomainError
from app.chapters.models import Chapter, ChapterStatus
from app.manuscript import service as manuscript
from app.rewriting import suggestions
from app.rewriting.context import capture_context
from app.rewriting.models import RewriteProposal
from app.rewriting.schemas import ApplyRead, ProposalRead, RewriteOutput
from app.stories.models import Story


def now():
    return datetime.now(UTC)


def expired(proposal):
    expiry = proposal.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    return expiry <= now()


async def lock_source(db, chapter, user_id):
    # Same chapter lock/order as all manuscript and planning writes.
    chapter = await db.scalar(
        select(Chapter)
        .where(Chapter.id == chapter.id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    story = await db.scalar(
        select(Story)
        .where(Story.id == chapter.story_id)
        .execution_options(populate_existing=True)
    )
    if chapter.is_archived or story.is_archived or story.user_id != user_id:
        raise DomainError(404, "Chapter not found")
    return chapter


async def get_proposal(db, chapter, turn_id, proposal_id, user_id, *, lock=False):
    await manuscript.get_turn(db, chapter.id, turn_id)
    query = (
        select(RewriteProposal)
        .where(
            RewriteProposal.id == proposal_id,
            RewriteProposal.turn_id == turn_id,
            RewriteProposal.user_id == user_id,
        )
        .execution_options(populate_existing=True)
    )
    if lock:
        query = query.with_for_update()
    proposal = await db.scalar(query)
    if proposal is None:
        raise DomainError(404, "Rewrite proposal not found")
    return proposal


async def list_proposals(db, chapter, turn_id, user_id):
    await manuscript.get_turn(db, chapter.id, turn_id)
    return list(
        (
            await db.scalars(
                select(RewriteProposal)
                .where(
                    RewriteProposal.turn_id == turn_id,
                    RewriteProposal.user_id == user_id,
                    RewriteProposal.expires_at > now(),
                    RewriteProposal.status.in_(["generating", "ready"]),
                )
                .order_by(RewriteProposal.created_at.desc(), RewriteProposal.id)
                .limit(10)
            )
        ).all()
    )


async def generate(db, chapter, turn_id, user_id, body):
    chapter = await lock_source(db, chapter, user_id)
    turn = await manuscript.get_turn(db, chapter.id, turn_id)
    existing = await db.get(RewriteProposal, body.proposal_id)
    if existing is not None:
        if existing.user_id != user_id or existing.turn_id != turn_id:
            raise DomainError(404, "Rewrite proposal not found")
        if (
            any(
                getattr(existing, key) != getattr(body, key)
                for key in ("start", "end", "instruction", "original_text")
            )
            or existing.base_turn_version != body.expected_version
        ):
            raise DomainError(409, "This proposal ID belongs to a different request.")
        if existing.status == "applied":
            return ProposalRead.model_validate(existing)
        if expired(existing) or existing.status == "cancelled":
            raise DomainError(
                410, "This proposal is no longer available. Generate a new suggestion."
            )
        if existing.status == "ready":
            return ProposalRead.model_validate(existing)
        raise DomainError(
            409,
            "Suggestion is still generating or failed. Check saved proposals, or generate a new suggestion.",
        )
    if chapter.status == ChapterStatus.locked:
        raise DomainError(409, "Unlock this chapter before rewriting text.")
    if (
        turn.version != body.expected_version
        or body.end > len(turn.content)
        or turn.content[body.start : body.end] != body.original_text
    ):
        raise DomainError(
            409, "The selected paragraph changed. Reload it and select the text again."
        )
    count = await db.scalar(
        select(func.count())
        .select_from(RewriteProposal)
        .where(
            RewriteProposal.user_id == user_id,
            RewriteProposal.status.in_(["generating", "ready"]),
            RewriteProposal.expires_at > now(),
        )
    )
    if count >= 20:
        raise DomainError(
            429,
            "You have 20 active rewrite proposals. Cancel unused suggestions or wait for expiry.",
        )
    context, context_version = await capture_context(
        db, chapter, turn, body.start, body.end
    )
    proposal = RewriteProposal(
        id=body.proposal_id,
        user_id=user_id,
        turn_id=turn_id,
        base_turn_version=turn.version,
        base_manuscript_revision=chapter.manuscript_revision,
        context_version=context_version,
        start=body.start,
        end=body.end,
        original_text=body.original_text,
        instruction=body.instruction,
        status="generating",
        expires_at=now() + timedelta(minutes=30),
    )
    db.add(proposal)
    try:
        await db.commit()
    except IntegrityError as error:
        await db.rollback()
        raise DomainError(
            409,
            "This proposal request is already being processed. Check saved proposals.",
        ) from error
    # No DB transaction/connection held while the model runs.
    try:
        output = RewriteOutput.model_validate(
            await suggestions.suggest(context, body.original_text, body.instruction)
        )
    except Exception as error:
        proposal = await db.scalar(
            select(RewriteProposal)
            .where(RewriteProposal.id == body.proposal_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if proposal.status == "generating":
            proposal.status = "failed"
            await db.commit()
        raise DomainError(
            502,
            "AI rewrite failed or returned invalid text. Your manuscript is unchanged. Try again.",
        ) from error
    proposal = await db.scalar(
        select(RewriteProposal)
        .where(RewriteProposal.id == body.proposal_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if proposal.status != "generating" or expired(proposal):
        raise DomainError(
            410, "This proposal was cancelled or expired. Your manuscript is unchanged."
        )
    proposal.proposed_text = output.proposed_text
    proposal.status = "ready"
    await db.commit()
    await db.refresh(proposal)
    return ProposalRead.model_validate(proposal)


async def apply(db, chapter, turn_id, proposal_id, user_id):
    chapter = await lock_source(db, chapter, user_id)
    proposal = await get_proposal(db, chapter, turn_id, proposal_id, user_id, lock=True)
    if proposal.status == "applied":
        return ApplyRead(
            proposal_id=proposal.id,
            applied_version=proposal.applied_version,
            applied_content=proposal.applied_content,
            already_applied=True,
        )
    if expired(proposal) or proposal.status == "cancelled":
        raise DomainError(
            410, "Proposal expired or was cancelled. Generate a new suggestion."
        )
    if proposal.status != "ready":
        raise DomainError(409, "Proposal is not ready to apply.")
    if chapter.status == ChapterStatus.locked:
        raise DomainError(409, "Unlock this chapter before applying a rewrite.")
    turn = await manuscript.get_turn(db, chapter.id, turn_id)
    if (
        turn.version != proposal.base_turn_version
        or chapter.manuscript_revision != proposal.base_manuscript_revision
        or turn.content[proposal.start : proposal.end] != proposal.original_text
    ):
        raise DomainError(
            409,
            "The manuscript changed after this suggestion. Reload and regenerate it.",
        )
    _, fingerprint = await capture_context(
        db, chapter, turn, proposal.start, proposal.end
    )
    if fingerprint != proposal.context_version:
        raise DomainError(
            409, "Story, cast, or planning context changed. Regenerate this suggestion."
        )
    replacement = (
        turn.content[: proposal.start]
        + proposal.proposed_text
        + turn.content[proposal.end :]
    )
    if not replacement.strip() or len(replacement) > 50000:
        raise DomainError(
            422,
            "The resulting paragraph must contain text and be at most 50000 characters.",
        )
    turn = await manuscript.stage_turn_edit(
        db,
        chapter,
        turn_id,
        replacement,
        proposal.base_turn_version,
        user_id,
        source="ai_rewrite",
    )
    proposal.status = "applied"
    proposal.applied_version, proposal.applied_content = turn.version, turn.content
    await db.commit()
    return ApplyRead(
        proposal_id=proposal.id,
        applied_version=proposal.applied_version,
        applied_content=proposal.applied_content,
        already_applied=False,
    )


async def cancel(db, chapter, turn_id, proposal_id, user_id):
    chapter = await lock_source(db, chapter, user_id)
    proposal = await get_proposal(db, chapter, turn_id, proposal_id, user_id, lock=True)
    if proposal.status == "applied":
        raise DomainError(
            409,
            "This rewrite is already applied. Use paragraph history to restore earlier text.",
        )
    proposal.status = "cancelled"
    await db.commit()
    return ProposalRead.model_validate(proposal)
