import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, uuid_pk


class ChapterStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    in_review = "in_review"
    complete = "complete"
    locked = "locked"


# allow-list of reachable next statuses per current status — enforced by
# app.core.status.assert_transition. `complete` and `locked` cannot be reached
# via generic PATCH (see chapters/service.py:update_chapter) since they carry
# side effects (summarization, edit-protection) that a bare field write would
# skip — only the dedicated /complete, /lock, /unlock paths reach them.
CHAPTER_TRANSITIONS: dict[ChapterStatus, set[ChapterStatus]] = {
    ChapterStatus.draft: {ChapterStatus.in_progress},
    ChapterStatus.in_progress: {ChapterStatus.in_review, ChapterStatus.complete, ChapterStatus.draft},
    ChapterStatus.in_review: {ChapterStatus.in_progress, ChapterStatus.draft},
    ChapterStatus.complete: {ChapterStatus.in_progress, ChapterStatus.locked},
    ChapterStatus.locked: {ChapterStatus.complete},
}


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = uuid_pk()
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("stories.id"), nullable=False, index=True
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ChapterStatus] = mapped_column(
        Enum(ChapterStatus, name="chapter_status"), default=ChapterStatus.draft, server_default="draft"
    )
    summary: Mapped[str | None] = mapped_column(Text)
    target_length_words: Mapped[int | None] = mapped_column(Integer)
    chapter_summary: Mapped[str | None] = mapped_column(Text)
    running_summary_cache: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    story: Mapped["Story"] = relationship("Story", back_populates="chapters")

    __table_args__ = (UniqueConstraint("story_id", "order_index", name="uq_chapter_order_per_story"),)


class ChapterCharacter(Base):
    __tablename__ = "chapter_characters"

    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id"), primary_key=True)
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id"), primary_key=True
    )
