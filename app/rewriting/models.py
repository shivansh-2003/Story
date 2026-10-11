import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, uuid_pk


class RewriteProposal(Base):
    __tablename__ = "rewrite_proposals"
    __table_args__ = (
        CheckConstraint('"start" >= 0 AND "end" > "start"', name="ck_rewrite_range"),
        CheckConstraint(
            "status IN ('generating','ready','failed','cancelled','applied')",
            name="ck_rewrite_status",
        ),
    )
    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), index=True
    )
    turn_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapter_turns.id"), index=True
    )
    base_turn_version: Mapped[int] = mapped_column(Integer)
    base_manuscript_revision: Mapped[int] = mapped_column(Integer)
    context_version: Mapped[str] = mapped_column(String(64))
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    original_text: Mapped[str] = mapped_column(Text)
    proposed_text: Mapped[str | None] = mapped_column(Text)
    instruction: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="generating")
    applied_version: Mapped[int | None] = mapped_column(Integer)
    applied_content: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
