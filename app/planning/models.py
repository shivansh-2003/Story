import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base, uuid_pk


class ChapterPlan(Base):
    __tablename__ = "chapter_plans"
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id"), primary_key=True
    )
    objective: Mapped[str] = mapped_column(Text, default="", server_default="")
    conflict: Mapped[str] = mapped_column(Text, default="", server_default="")
    ending_beat: Mapped[str] = mapped_column(Text, default="", server_default="")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class Scene(Base):
    __tablename__ = "scenes"
    id: Mapped[uuid.UUID] = uuid_pk()
    chapter_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapters.id"), index=True
    )
    order_index: Mapped[int] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(Text)
    goal: Mapped[str] = mapped_column(Text, default="", server_default="")
    conflict: Mapped[str] = mapped_column(Text, default="", server_default="")
    outcome: Mapped[str] = mapped_column(Text, default="", server_default="")
    setting: Mapped[str] = mapped_column(Text, default="", server_default="")
    notes: Mapped[str] = mapped_column(Text, default="", server_default="")
    pov_character_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id")
    )
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    is_archived: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    __table_args__ = (
        UniqueConstraint("chapter_id", "order_index", name="uq_scene_order"),
    )


class SceneCharacter(Base):
    __tablename__ = "scene_characters"
    scene_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scenes.id"), primary_key=True
    )
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id"), primary_key=True
    )
