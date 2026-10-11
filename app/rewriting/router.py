import uuid

from fastapi import APIRouter

from app.core.deps import CurrentUser, DbSession, RateLimitedUser, get_owned_chapter
from app.rewriting import service
from app.rewriting.schemas import ApplyRead, ProposalRead, RewriteRequest

router = APIRouter(
    prefix="/stories/{story_id}/chapters/{chapter_id}/turns/{turn_id}/rewrite-proposals",
    tags=["rewriting"],
)


@router.post("", response_model=ProposalRead, status_code=201)
async def generate(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    turn_id: uuid.UUID,
    body: RewriteRequest,
    db: DbSession,
    user: RateLimitedUser,
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    return await service.generate(db, chapter, turn_id, user.id, body)


@router.get("", response_model=list[ProposalRead])
async def proposals(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    turn_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    return await service.list_proposals(db, chapter, turn_id, user.id)


@router.get("/{proposal_id}", response_model=ProposalRead)
async def proposal(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    turn_id: uuid.UUID,
    proposal_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    return await service.get_proposal(db, chapter, turn_id, proposal_id, user.id)


@router.post("/{proposal_id}/apply", response_model=ApplyRead)
async def apply(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    turn_id: uuid.UUID,
    proposal_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    return await service.apply(db, chapter, turn_id, proposal_id, user.id)


@router.post("/{proposal_id}/cancel", response_model=ProposalRead)
async def cancel(
    story_id: uuid.UUID,
    chapter_id: uuid.UUID,
    turn_id: uuid.UUID,
    proposal_id: uuid.UUID,
    db: DbSession,
    user: CurrentUser,
):
    chapter = await get_owned_chapter(db, story_id, chapter_id, user)
    return await service.cancel(db, chapter, turn_id, proposal_id, user.id)
