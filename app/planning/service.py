import uuid

from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.chapters.models import Chapter
from app.characters.models import Character
from app.manuscript.service import lock_chapter
from app.planning.models import ChapterPlan, Scene, SceneCharacter
from app.planning.schemas import (
    PlanFields,
    PlanRead,
    PlanUpdate,
    ProposalSave,
    SceneFields,
    SceneRead,
    SceneReorder,
    SceneUpdate,
)
from app.stories.models import StoryCharacter


async def plan_read(db: AsyncSession, chapter: Chapter) -> PlanRead:
    plan = await db.get(ChapterPlan, chapter.id)
    fields = (
        {name: getattr(plan, name) for name in PlanFields.model_fields} if plan else {}
    )
    return PlanRead(
        chapter_id=chapter.id,
        version=plan.version if plan else 0,
        planning_revision=chapter.planning_revision,
        **fields,
    )


async def save_plan(
    db: AsyncSession, chapter: Chapter, body: PlanUpdate, *, commit=True
) -> PlanRead:
    chapter = await lock_chapter(db, chapter)
    plan = await db.get(ChapterPlan, chapter.id, populate_existing=True)
    if body.expected_version != (plan.version if plan else 0):
        raise HTTPException(
            409, "The chapter plan changed. Reload the latest plan before saving."
        )
    fields = body.model_dump(exclude={"expected_version"}, exclude_unset=True)
    if plan and all(getattr(plan, key) == value for key, value in fields.items()):
        return await plan_read(db, chapter)
    if plan is None:
        plan = ChapterPlan(chapter_id=chapter.id, version=1, **fields)
        db.add(plan)
    else:
        for key, value in fields.items():
            setattr(plan, key, value)
        plan.version += 1
    chapter.planning_revision += 1
    await db.flush()
    if commit:
        await db.commit()
    return await plan_read(db, chapter)


async def get_scene(
    db: AsyncSession,
    chapter_id: uuid.UUID,
    scene_id: uuid.UUID,
    *,
    allow_archived=False,
) -> Scene:
    scene = await db.scalar(
        select(Scene)
        .where(Scene.id == scene_id, Scene.chapter_id == chapter_id)
        .execution_options(populate_existing=True)
    )
    if scene is None or (scene.is_archived and not allow_archived):
        raise HTTPException(404, "Scene not found in this chapter")
    return scene


async def validate_cast(
    db: AsyncSession, chapter: Chapter, ids: list[uuid.UUID]
) -> None:
    if not ids:
        return
    found = set(
        (
            await db.scalars(
                select(Character.id)
                .join(StoryCharacter, StoryCharacter.character_id == Character.id)
                .where(
                    StoryCharacter.story_id == chapter.story_id,
                    Character.is_archived.is_(False),
                    Character.id.in_(ids),
                )
            )
        ).all()
    )
    if found != set(ids):
        raise HTTPException(
            422,
            "Every scene character must be an active character imported into this story.",
        )


async def scenes_read(db: AsyncSession, chapter: Chapter) -> list[SceneRead]:
    scenes = (
        await db.scalars(
            select(Scene)
            .where(Scene.chapter_id == chapter.id, Scene.is_archived.is_(False))
            .order_by(Scene.order_index)
        )
    ).all()
    ids = [s.id for s in scenes]
    links = (
        (
            await db.execute(
                select(SceneCharacter.scene_id, SceneCharacter.character_id).where(
                    SceneCharacter.scene_id.in_(ids)
                )
            )
        ).all()
        if ids
        else []
    )
    cast = {scene.id: [] for scene in scenes}
    for scene_id, character_id in links:
        cast[scene_id].append(character_id)
    return [
        SceneRead(
            id=s.id,
            chapter_id=s.chapter_id,
            order_index=s.order_index,
            version=s.version,
            updated_at=s.updated_at,
            character_ids=sorted(cast[s.id], key=str),
            **{
                key: getattr(s, key)
                for key in SceneFields.model_fields
                if key != "character_ids"
            },
        )
        for s in scenes
    ]


async def create_scene(
    db: AsyncSession, chapter: Chapter, body: SceneFields, *, commit=True
) -> Scene:
    chapter = await lock_chapter(db, chapter)
    await validate_cast(db, chapter, body.character_ids)
    if (
        await db.scalar(
            select(func.count())
            .select_from(Scene)
            .where(Scene.chapter_id == chapter.id, Scene.is_archived.is_(False))
        )
        >= 100
    ):
        raise HTTPException(422, "A chapter can have at most 100 active scenes.")
    order = await db.scalar(
        select(func.coalesce(func.max(Scene.order_index), -1) + 1).where(
            Scene.chapter_id == chapter.id, Scene.is_archived.is_(False)
        )
    )
    scene = Scene(
        id=uuid.uuid4(),
        chapter_id=chapter.id,
        order_index=order,
        version=1,
        **body.model_dump(exclude={"character_ids"}),
    )
    db.add(scene)
    await db.flush()
    db.add_all(
        [
            SceneCharacter(scene_id=scene.id, character_id=id)
            for id in body.character_ids
        ]
    )
    chapter.planning_revision += 1
    await db.flush()
    if commit:
        await db.commit()
    return scene


async def update_scene(
    db: AsyncSession, chapter: Chapter, scene_id: uuid.UUID, body: SceneUpdate
) -> None:
    chapter = await lock_chapter(db, chapter)
    scene = await get_scene(db, chapter.id, scene_id)
    if scene.version != body.expected_version:
        raise HTTPException(
            409, "This scene changed. Reload the latest scene before saving."
        )
    current_cast = set(
        (
            await db.scalars(
                select(SceneCharacter.character_id).where(
                    SceneCharacter.scene_id == scene.id
                )
            )
        ).all()
    )
    merged = {
        key: getattr(scene, key)
        for key in SceneFields.model_fields
        if key != "character_ids"
    }
    merged["character_ids"] = list(current_cast)
    merged.update(body.model_dump(exclude={"expected_version"}, exclude_unset=True))
    try:
        validated = SceneFields.model_validate(merged)
    except ValidationError as error:
        raise HTTPException(
            422,
            "Invalid scene details. Use a nonblank title, valid text fields, and a POV included in the scene cast.",
        ) from error
    await validate_cast(db, chapter, validated.character_ids)
    fields = validated.model_dump(exclude={"character_ids"})
    if current_cast == set(validated.character_ids) and all(
        getattr(scene, key) == value for key, value in fields.items()
    ):
        return
    for key, value in fields.items():
        setattr(scene, key, value)
    await db.execute(delete(SceneCharacter).where(SceneCharacter.scene_id == scene.id))
    db.add_all(
        [
            SceneCharacter(scene_id=scene.id, character_id=id)
            for id in validated.character_ids
        ]
    )
    scene.version += 1
    chapter.planning_revision += 1
    await db.commit()


async def archive_scene(
    db: AsyncSession, chapter: Chapter, scene_id: uuid.UUID, expected_version: int
) -> None:
    chapter = await lock_chapter(db, chapter)
    scene = await get_scene(db, chapter.id, scene_id)
    if scene.version != expected_version:
        raise HTTPException(409, "This scene changed. Reload it before removing it.")
    smallest = await db.scalar(
        select(func.min(Scene.order_index)).where(Scene.chapter_id == chapter.id)
    )
    scene.order_index = min(smallest or 0, 0) - 1
    scene.is_archived = True
    scene.version += 1
    chapter.planning_revision += 1
    await db.commit()


async def reorder_scenes(
    db: AsyncSession, chapter: Chapter, body: SceneReorder
) -> None:
    chapter = await lock_chapter(db, chapter)
    if chapter.planning_revision != body.expected_planning_revision:
        raise HTTPException(
            409, "Planning changed. Reload the scenes before reordering."
        )
    scenes = (
        await db.scalars(
            select(Scene).where(
                Scene.chapter_id == chapter.id, Scene.is_archived.is_(False)
            )
        )
    ).all()
    by_id = {scene.id: scene for scene in scenes}
    if len(set(body.scene_ids)) != len(body.scene_ids) or set(body.scene_ids) != set(
        by_id
    ):
        raise HTTPException(
            422, "Reorder must include every active scene exactly once."
        )
    if all(by_id[id].order_index == i for i, id in enumerate(body.scene_ids)):
        return
    smallest = await db.scalar(
        select(func.min(Scene.order_index)).where(Scene.chapter_id == chapter.id)
    )
    for i, id in enumerate(body.scene_ids):
        by_id[id].order_index = min(smallest or 0, 0) - i - 1
    await db.flush()
    for i, id in enumerate(body.scene_ids):
        by_id[id].order_index = i
    chapter.planning_revision += 1
    await db.commit()


async def save_proposal(
    db: AsyncSession, chapter: Chapter, body: ProposalSave
) -> PlanRead:
    chapter = await lock_chapter(db, chapter)
    if (
        chapter.planning_revision != body.expected_planning_revision
        or chapter.manuscript_revision != body.expected_manuscript_revision
    ):
        raise HTTPException(
            409,
            "The manuscript or planning changed after this suggestion. Reload before saving it.",
        )
    await save_plan(
        db,
        chapter,
        PlanUpdate(
            expected_version=body.expected_plan_version, **body.plan.model_dump()
        ),
        commit=False,
    )
    for scene in body.scenes:
        await create_scene(db, chapter, scene, commit=False)
    await db.commit()
    return await plan_read(db, chapter)


async def generation_context(
    db: AsyncSession, chapter: Chapter, scene_id: uuid.UUID | None
) -> dict:
    plan = await plan_read(db, chapter)
    text = ""
    fields = [
        (name.replace("_", " ").title(), getattr(plan, name))
        for name in PlanFields.model_fields
    ]
    if any(value for _, value in fields):
        text = "Chapter plan (intended events, not established facts):\n" + "\n".join(
            f"{key}: {value}" for key, value in fields if value
        )
    characters = None
    if scene_id is not None:
        scene = await get_scene(db, chapter.id, scene_id)
        characters = list(
            (
                await db.scalars(
                    select(Character)
                    .join(SceneCharacter, SceneCharacter.character_id == Character.id)
                    .join(StoryCharacter, StoryCharacter.character_id == Character.id)
                    .where(
                        SceneCharacter.scene_id == scene.id,
                        StoryCharacter.story_id == chapter.story_id,
                        Character.is_archived.is_(False),
                    )
                    .order_by(Character.name, Character.id)
                )
            ).all()
        )
        pov = next((c.name for c in characters if c.id == scene.pov_character_id), None)
        text += "\n\nSelected scene (intended events):\n" + "\n".join(
            f"{key}: {value}"
            for key, value in [
                ("Title", scene.title),
                ("Goal", scene.goal),
                ("Conflict", scene.conflict),
                ("Outcome", scene.outcome),
                ("Setting", scene.setting),
                ("POV", pov),
                ("Notes", scene.notes),
            ]
            if value
        )
    return {
        "text": text.strip(),
        "characters": characters,
        "scene_id": str(scene_id) if scene_id else None,
        "planning_revision": chapter.planning_revision,
    }
