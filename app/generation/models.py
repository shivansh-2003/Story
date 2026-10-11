import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, uuid_pk


class ChapterTurn(Base):
    """Current accepted paragraph; previous contents live in TurnRevision."""

    __tablename__ = "chapter_turns"

    id: Mapped[uuid.UUID] = uuid_pk()
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    instruction: Mapped[str | None] = mapped_column(Text)
    scene_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("scenes.id"), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1", nullable=False)
    source: Mapped[str] = mapped_column(Text, default="ai", server_default="ai", nullable=False)
    accepted_draft_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), unique=True)
    embedding_version: Mapped[int | None] = mapped_column(Integer)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    __table_args__ = (UniqueConstraint("chapter_id", "sequence", name="uq_turn_sequence"),)
    # matches OpenAI text-embedding-3-small's output dimension. Nullable:
    # pre-feature rows and any turn whose embedding job failed stay NULL,
    # excluded from search rather than blocking accept on embedding latency.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
