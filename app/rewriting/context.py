import hashlib
import json

from sqlalchemy import select

from app.characters.queries import chapter_cast, scene_cast, cast_relationships
from app.core.errors import DomainError
from app.generation.models import ChapterTurn
from app.planning.service import generation_context
from app.stories.models import Story


async def capture_context(db, chapter, turn, start, end):
    story = await db.scalar(
        select(Story)
        .where(Story.id == chapter.story_id)
        .execution_options(populate_existing=True)
    )
    # Accepted paragraphs retain links to archived scenes; those remain useful context.
    from app.planning.models import Scene

    scene = await db.get(Scene, turn.scene_id) if turn.scene_id else None
    planning = await generation_context(db, chapter, None)
    scene_source = None
    if scene is not None and scene.chapter_id == chapter.id:
        scene_source = {
            key: getattr(scene, key)
            for key in (
                "id",
                "title",
                "goal",
                "conflict",
                "outcome",
                "setting",
                "notes",
                "pov_character_id",
                "version",
                "is_archived",
            )
        }
        planning["characters"] = await scene_cast(db, chapter.story_id, scene.id)
    cast = planning["characters"]
    if cast is None:
        cast = await chapter_cast(db, chapter.id, limit=51)
    cast = sorted(cast, key=lambda c: str(c.id))
    if len(cast) > 50:

        raise DomainError(
            422,
            "Rewrite context supports up to 50 active characters. Reduce the chapter or scene cast.",
        )
    ids = [c.id for c in cast]
    relations = await cast_relationships(db, ids)
    before = list(
        (
            await db.scalars(
                select(ChapterTurn.content)
                .where(
                    ChapterTurn.chapter_id == chapter.id,
                    ChapterTurn.sequence < turn.sequence,
                )
                .order_by(ChapterTurn.sequence.desc())
                .limit(2)
            )
        ).all()
    )
    after = list(
        (
            await db.scalars(
                select(ChapterTurn.content)
                .where(
                    ChapterTurn.chapter_id == chapter.id,
                    ChapterTurn.sequence > turn.sequence,
                )
                .order_by(ChapterTurn.sequence)
                .limit(2)
            )
        ).all()
    )
    fields = (
        "title",
        "genre",
        "tone",
        "pov",
        "tense",
        "rating",
        "premise",
        "setting",
        "themes",
        "content_boundaries",
        "writing_style_notes",
        "target_audience",
        "is_archived",
    )
    character_fields = (
        "name",
        "role",
        "age",
        "pronouns",
        "appearance",
        "voice_notes",
        "personality_traits",
        "motivation",
        "flaw",
        "backstory",
        "is_archived",
    )
    source = {
        "story": {key: getattr(story, key) for key in fields},
        "chapter_title": chapter.title,
        "manuscript_revision": chapter.manuscript_revision,
        "planning_revision": chapter.planning_revision,
        "scene_id": turn.scene_id,
        "scene": scene_source,
        "characters": [
            {"id": c.id, **{key: getattr(c, key) for key in character_fields}}
            for c in cast
        ],
        "relationships": [
            {
                "from": r.character_id,
                "to": r.related_character_id,
                "label": r.relationship_label,
            }
            for r in relations
        ],
        "planning": planning["text"],
    }
    fingerprint = hashlib.sha256(
        json.dumps(source, sort_keys=True, default=str, ensure_ascii=False).encode()
    ).hexdigest()

    # Bound inference input while fingerprinting the full authoritative fields.
    def bounded(value):
        if isinstance(value, dict):
            return {key: bounded(item) for key, item in value.items()}
        if isinstance(value, list):
            return [bounded(item) for item in value[:50]]
        return str(value)[:1000] if value is not None else None

    context = {
        **bounded(source),
        "before": ("\n\n".join(reversed(before)) + "\n\n" + turn.content[:start])[
            -4000:
        ],
        "after": (turn.content[end:] + "\n\n" + "\n\n".join(after))[:4000],
    }
    if len(json.dumps(context, default=str)) > 60000:

        raise DomainError(
            422,
            "Rewrite context is too large. Reduce the active cast or character details.",
        )
    return context, fingerprint
