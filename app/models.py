import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    ARRAY,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


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


class ChapterStatus(str, enum.Enum):
    draft = "draft"
    in_progress = "in_progress"
    complete = "complete"


class TurnStatus(str, enum.Enum):
    pending = "pending"
    accepted = "accepted"
    superseded = "superseded"
    edited = "edited"


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = uuid_pk()
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    hashed_password: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    characters: Mapped[list["Character"]] = relationship(back_populates="user")
    stories: Mapped[list["Story"]] = relationship(back_populates="user")


class Character(Base):
    __tablename__ = "characters"

    id: Mapped[uuid.UUID] = uuid_pk()
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    role: Mapped[str | None] = mapped_column(Text)
    age: Mapped[str | None] = mapped_column(Text)
    pronouns: Mapped[str | None] = mapped_column(Text)
    appearance: Mapped[str | None] = mapped_column(Text)
    voice_notes: Mapped[str | None] = mapped_column(Text)
    personality_traits: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    motivation: Mapped[str | None] = mapped_column(Text)
    flaw: Mapped[str | None] = mapped_column(Text)
    backstory: Mapped[str | None] = mapped_column(Text)
    condensed_summary: Mapped[str | None] = mapped_column(Text)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped["User"] = relationship(back_populates="characters")


class CharacterRelationship(Base):
    __tablename__ = "character_relationships"

    id: Mapped[uuid.UUID] = uuid_pk()
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False
    )
    related_character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id"), nullable=False
    )
    relationship_label: Mapped[str | None] = mapped_column(Text)


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

    user: Mapped["User"] = relationship(back_populates="stories")
    chapters: Mapped[list["Chapter"]] = relationship(back_populates="story")


class StoryCharacter(Base):
    __tablename__ = "story_characters"

    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id"), primary_key=True)
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id"), primary_key=True
    )


class Chapter(Base):
    __tablename__ = "chapters"

    id: Mapped[uuid.UUID] = uuid_pk()
    story_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("stories.id"), nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ChapterStatus] = mapped_column(
        Enum(ChapterStatus, name="chapter_status"), default=ChapterStatus.draft, server_default="draft"
    )
    summary: Mapped[str | None] = mapped_column(Text)
    target_length_words: Mapped[int | None] = mapped_column(Integer)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    story: Mapped["Story"] = relationship(back_populates="chapters")

    __table_args__ = (UniqueConstraint("story_id", "order_index", name="uq_chapter_order_per_story"),)


class ChapterCharacter(Base):
    __tablename__ = "chapter_characters"

    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id"), primary_key=True)
    character_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("characters.id"), primary_key=True
    )


class ChapterTurn(Base):
    __tablename__ = "chapter_turns"

    id: Mapped[uuid.UUID] = uuid_pk()
    chapter_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chapters.id"), nullable=False)
    parent_turn_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("chapter_turns.id")
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    original_content: Mapped[str | None] = mapped_column(Text)
    status: Mapped[TurnStatus] = mapped_column(
        Enum(TurnStatus, name="turn_status"), default=TurnStatus.pending, server_default="pending"
    )
    instruction: Mapped[str | None] = mapped_column(Text)
    length_setting: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
