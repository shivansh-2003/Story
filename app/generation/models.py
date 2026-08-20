import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, uuid_pk


class ChapterTurn(Base):
    """One row per ACCEPTED paragraph. Append-only — the working draft (pending
    turn, sibling attempts) lives in Redis via session_store, not here."""

    __tablename__ = "chapter_turns"

    id: Mapped[uuid.UUID] = uuid_pk()
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False, index=True
    )
    sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    instruction: Mapped[str | None] = mapped_column(Text)
    # matches OpenAI text-embedding-3-small's output dimension. Nullable:
    # pre-feature rows and any turn whose embedding job failed stay NULL,
    # excluded from search rather than blocking accept on embedding latency.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1536))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
