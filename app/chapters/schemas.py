import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.chapters.models import ChapterStatus
from app.manuscript.schemas import TurnRead


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
    turns: list[TurnRead] = []
    manuscript_revision: int = 0
    planning_revision: int = 0


class ChapterReorderItem(BaseModel):
    chapter_id: uuid.UUID
    order_index: int


class ChapterReorderRequest(BaseModel):
    items: list[ChapterReorderItem]
