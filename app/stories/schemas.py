import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.characters.schemas import CharacterRead
from app.stories.models import POV, StoryStatus, Tense


class StoryBase(BaseModel):
    title: str
    genre: list[str] | None = None
    tone: str | None = None
    pov: POV | None = None
    tense: Tense | None = None
    rating: str | None = None
    premise: str | None = None
    opening_line: str | None = None
    setting: str | None = None
    themes: list[str] | None = None
    content_boundaries: str | None = None
    writing_style_notes: str | None = None
    target_audience: str | None = None


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
    setting: str | None = None
    themes: list[str] | None = None
    content_boundaries: str | None = None
    writing_style_notes: str | None = None
    target_audience: str | None = None
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
