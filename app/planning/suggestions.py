from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import Chapter
from app.characters.models import Character
from app.core.llm_client import call_json_model
from app.generation.models import ChapterTurn
from app.planning.prompts import suggestion_prompt
from app.planning.schemas import PlanProposal, ProposalRead
from app.planning.service import plan_read, scenes_read
from app.stories.models import Story, StoryCharacter


async def suggest(
    db: AsyncSession, chapter: Chapter, story: Story, instruction: str
) -> ProposalRead:
    plan = await plan_read(db, chapter)
    scenes = await scenes_read(db, chapter)
    cast = list(
        (
            await db.scalars(
                select(Character)
                .join(StoryCharacter, StoryCharacter.character_id == Character.id)
                .where(
                    StoryCharacter.story_id == story.id,
                    Character.is_archived.is_(False),
                )
                .order_by(Character.name, Character.id)
                .limit(50)
            )
        ).all()
    )
    recent = list(
        (
            await db.scalars(
                select(ChapterTurn.content)
                .where(ChapterTurn.chapter_id == chapter.id)
                .order_by(ChapterTurn.sequence.desc())
                .limit(4)
            )
        ).all()
    )
    context = {
        "story": {
            key: (getattr(story, key) or "")[:2000]
            for key in (
                "title",
                "premise",
                "tone",
                "setting",
                "writing_style_notes",
                "content_boundaries",
            )
        },
        "chapter_title": (chapter.title or "")[:200],
        "current_plan": plan.model_dump(mode="json"),
        "existing_scenes": [
            {"title": s.title, "goal": s.goal[:300]} for s in scenes[:20]
        ],
        "story_cast": [
            {"id": str(c.id), "name": c.name[:200], "role": (c.role or "")[:200]}
            for c in cast
        ],
        "recent_accepted_prose": "\n\n".join(reversed(recent))[-6000:],
    }
    chapter_id, plan_version, planning_revision, manuscript_revision = (
        chapter.id,
        plan.version,
        chapter.planning_revision,
        chapter.manuscript_revision,
    )
    valid_ids = {c.id for c in cast}
    # Release the read transaction/connection before the potentially slow model call.
    await db.rollback()
    system, user = suggestion_prompt(context, instruction)
    try:
        proposal = await call_json_model(
            user, PlanProposal, max_tokens=2400, system=system
        )
        if any(
            not set(scene.character_ids).issubset(valid_ids)
            for scene in proposal.scenes
        ):
            raise ValueError("Proposal references unavailable story characters")
    except Exception as error:
        raise HTTPException(
            502,
            "AI planning suggestion failed or returned an invalid proposal. Your saved plans are unchanged; try again or plan manually.",
        ) from error
    return ProposalRead(
        **proposal.model_dump(),
        chapter_id=chapter_id,
        expected_plan_version=plan_version,
        expected_planning_revision=planning_revision,
        expected_manuscript_revision=manuscript_revision,
    )
