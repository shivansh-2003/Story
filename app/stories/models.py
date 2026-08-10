import enum
import uuid
from datetime import datetime

from sqlalchemy import ARRAY, Boolean, DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base, uuid_pk


class POV(str, enum.Enum):
    first_person = "first_person"
    third_limited = "third_limited"
    third_omniscient = "third_omniscient"


class Tense(str, enum.Enum):
    past = "past"
    present = "present"


class StoryStatus(str, enum.Enum):
    draft = "draft"
    ongoing = "ongoing"
    completed = "completed"
    abandoned = "abandoned"


class Story(Base):
    __tablename__ = "stories"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    genre: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    tone: Mapped[str | None] = mapped_column(Text)
    pov: Mapped[POV | None] = mapped_column(Enum(POV, name="pov"))
    tense: Mapped[Tense | None] = mapped_column(Enum(Tense, name="tense"))
    rating: Mapped[str | None] = mapped_column(Text)
    premise: Mapped[str | None] = mapped_column(Text)
    opening_line: Mapped[str | None] = mapped_column(Text)
    status: Mapped[StoryStatus] = mapped_column(
        Enum(StoryStatus, name="story_status"), default=StoryStatus.draft, server_default="draft"
    )
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship("User", back_populates="stories")
    chapters: Mapped[list["Chapter"]] = relationship("Chapter", back_populates="story")


class StoryCharacter(Base):
    __tablename__ = "story_characters"

    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id"), primary_key=True)
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id"), primary_key=True
    )
