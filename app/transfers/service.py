import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import DomainError
from app.core.access import get_owned_story
from app.chapters.models import Chapter
from app.config import get_settings

from app.generation.models import ChapterTurn
from app.manuscript.service import append_imported_paragraphs
from app.stories.models import Story
from app.transfers.models import ImportPreview
from app.transfers.parsers import parse_manuscript
from app.transfers.schemas import ImportCommit, ImportResult, PreviewRead
from app.users.models import User


async def create_preview(
    db: AsyncSession, story_id: uuid.UUID, user: User, filename: str, data: bytes
) -> PreviewRead:
    chapters = parse_manuscript(filename, data)
    now = datetime.now(UTC)
    # Cleanup is scoped to this writer and never removes committed receipts.
    await db.execute(
        delete(ImportPreview).where(
            ImportPreview.user_id == user.id,
            ImportPreview.commit_key.is_(None),
            ImportPreview.expires_at <= now,
        )
    )
    active = await db.scalar(
        select(func.count())
        .select_from(ImportPreview)
        .where(
            ImportPreview.user_id == user.id,
            ImportPreview.commit_key.is_(None),
        )
    )
    if active >= 10:
        raise DomainError(
            429, "Too many open import previews. Cancel one or wait for it to expire."
        )
    preview = ImportPreview(
        user_id=user.id,
        story_id=story_id,
        chapters=[c.model_dump() for c in chapters],
        expires_at=now + timedelta(minutes=get_settings().import_preview_ttl_minutes),
    )
    db.add(preview)
    await db.commit()
    return PreviewRead(
        preview_token=preview.id,
        expires_at=preview.expires_at,
        chapters=chapters,
        paragraph_count=sum(len(c.paragraphs) for c in chapters),
    )


async def commit_import(
    db: AsyncSession, story_id: uuid.UUID, user: User, body: ImportCommit
) -> ImportResult:
    # Shared story lock serializes chapter order allocation and commit-key reuse.
    await get_owned_story(db, story_id, user, for_update=True)
    preview = await db.scalar(
        select(ImportPreview)
        .where(
            ImportPreview.id == body.preview_token,
            ImportPreview.story_id == story_id,
            ImportPreview.user_id == user.id,
        )
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    if preview is None:
        raise DomainError(404, "Import preview not found")
    request_hash = hashlib.sha256(
        json.dumps(body.model_dump(mode="json"), sort_keys=True).encode()
    ).hexdigest()
    if preview.commit_key is not None:
        if (
            preview.commit_key != body.commit_key
            or preview.request_hash != request_hash
        ):
            raise DomainError(
                409, "This preview was already imported with different options."
            )
        return ImportResult.model_validate(preview.result)
    if preview.expires_at.replace(tzinfo=UTC) <= datetime.now(UTC):
        raise DomainError(410, "Import preview expired. Upload the file again.")
    if await db.scalar(
        select(ImportPreview.id).where(
            ImportPreview.story_id == story_id,
            ImportPreview.commit_key == body.commit_key,
        )
    ):
        raise DomainError(
            409, "This import key was already used for another preview."
        )
    indices = [c.source_index for c in body.chapters]
    if len(set(indices)) != len(indices) or any(
        i >= len(preview.chapters) for i in indices
    ):
        raise DomainError(
            422, "Select each source chapter at most once using its preview index."
        )
    settings = get_settings()
    count = sum(len(preview.chapters[i]["paragraphs"]) for i in indices)
    if (
        len(indices) > settings.import_max_chapters
        or not 0 < count <= settings.import_max_paragraphs
    ):
        raise DomainError(422, "Selection is empty or exceeds the import limits.")
    next_order = await db.scalar(
        select(func.coalesce(func.max(Chapter.order_index), -1) + 1).where(
            Chapter.story_id == story_id
        )
    )
    result_chapters = []
    for offset, mapping in enumerate(body.chapters):
        paragraphs = preview.chapters[mapping.source_index]["paragraphs"]
        chapter = Chapter(
            id=uuid.uuid4(),
            story_id=story_id,
            title=mapping.title,
            order_index=next_order + offset,
            manuscript_revision=0,
            memory_revision=0,
        )
        db.add(chapter)
        await db.flush()
        await append_imported_paragraphs(
            db, chapter, paragraphs, user.id, body.enrich_with_ai
        )
        result_chapters.append(
            dict(id=chapter.id, title=chapter.title, paragraph_count=len(paragraphs))
        )
    result = ImportResult(
        chapters=result_chapters,
        paragraph_count=count,
        ai_enrichment_requested=body.enrich_with_ai,
    )
    preview.commit_key = body.commit_key
    preview.request_hash = request_hash
    preview.result = result.model_dump(mode="json")
    # Keep the receipt for safe retries without retaining a second manuscript copy.
    preview.chapters = []
    await db.commit()
    return result


async def cancel_preview(
    db: AsyncSession, story_id: uuid.UUID, user: User, token: uuid.UUID
) -> None:
    await db.execute(
        delete(ImportPreview).where(
            ImportPreview.id == token,
            ImportPreview.story_id == story_id,
            ImportPreview.user_id == user.id,
            ImportPreview.commit_key.is_(None),
        )
    )
    await db.commit()


async def read_export(
    db: AsyncSession, story_id: uuid.UUID, user: User, include_archived: bool
) -> tuple[str, list[dict]]:
    # One statement gives a consistent PostgreSQL snapshot of title/order/text.
    chapter_filter = Chapter.story_id == Story.id
    if not include_archived:
        chapter_filter &= Chapter.is_archived.is_(False)
    rows = (
        await db.execute(
            select(
                Story.title,
                Chapter.id,
                Chapter.title.label("chapter_title"),
                ChapterTurn.content,
            )
            .select_from(Story)
            .outerjoin(Chapter, chapter_filter)
            .outerjoin(ChapterTurn, ChapterTurn.chapter_id == Chapter.id)
            .where(
                Story.id == story_id,
                Story.user_id == user.id,
                Story.is_archived.is_(False),
            )
            .order_by(Chapter.order_index, ChapterTurn.sequence)
        )
    ).all()
    if not rows:
        raise DomainError(404, "Story not found")
    chapters = {}
    for row in rows:
        if row.id is not None:
            chapter = chapters.setdefault(
                row.id, {"title": row.chapter_title, "paragraphs": []}
            )
            if row.content is not None:
                chapter["paragraphs"].append(row.content)
    return rows[0].title, list(chapters.values())
