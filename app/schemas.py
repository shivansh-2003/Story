import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import ChapterStatus, POV, StoryStatus, Tense


# ---- auth ----


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    created_at: datetime


# ---- characters ----


class CharacterBase(BaseModel):
    name: str
    role: str | None = None
    age: str | None = None
    pronouns: str | None = None
    appearance: str | None = None
    voice_notes: str | None = None
    personality_traits: list[str] | None = None
    motivation: str | None = None
    flaw: str | None = None
    backstory: str | None = None


class CharacterCreate(CharacterBase):
    pass


class CharacterUpdate(BaseModel):
    name: str | None = None
    role: str | None = None
    age: str | None = None
    pronouns: str | None = None
    appearance: str | None = None
    voice_notes: str | None = None
    personality_traits: list[str] | None = None
    motivation: str | None = None
    flaw: str | None = None
    backstory: str | None = None


class CharacterRead(CharacterBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    condensed_summary: str | None
    is_archived: bool
    created_at: datetime
    updated_at: datetime


class CharacterRelationshipCreate(BaseModel):
    related_character_id: uuid.UUID
    relationship_label: str | None = None


class CharacterRelationshipRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    character_id: uuid.UUID
    related_character_id: uuid.UUID
    relationship_label: str | None


# ---- stories ----


class StoryBase(BaseModel):
    title: str
    genre: list[str] | None = None
    tone: str | None = None
    pov: POV | None = None
    tense: Tense | None = None
    rating: str | None = None
    premise: str | None = None
    opening_line: str | None = None


class StoryCreate(StoryBase):
    pass


class StoryUpdate(BaseModel):
    title: str | None = None
    genre: list[str] | None = None
    tone: str | None = None
    pov: POV | None = None
    tense: Tense | None = None
    rating: str | None = None
    premise: str | None = None
    opening_line: str | None = None
    status: StoryStatus | None = None


class StoryRead(StoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    status: StoryStatus
    created_at: datetime
    updated_at: datetime


class StoryDetailRead(StoryRead):
    characters: list[CharacterRead] = []


# ---- chapters ----


class ChapterBase(BaseModel):
    title: str | None = None
    target_length_words: int | None = None


class ChapterCreate(ChapterBase):
    pass


class ChapterUpdate(BaseModel):
    title: str | None = None
    status: ChapterStatus | None = None
    summary: str | None = None
    target_length_words: int | None = None


class ChapterRead(ChapterBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    story_id: uuid.UUID
    order_index: int
    status: ChapterStatus
    summary: str | None
    created_at: datetime
    updated_at: datetime


class ChapterDetailRead(ChapterRead):
    body: str = ""


class ChapterReorderItem(BaseModel):
    chapter_id: uuid.UUID
    order_index: int


class ChapterReorderRequest(BaseModel):
    items: list[ChapterReorderItem]
