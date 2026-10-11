import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class PreviewChapter(BaseModel):
    index: int
    title: str
    paragraphs: list[str]


class PreviewRead(BaseModel):
    preview_token: uuid.UUID
    expires_at: datetime
    chapters: list[PreviewChapter]
    paragraph_count: int


class ChapterMapping(BaseModel):
    source_index: int = Field(ge=0)
    title: str = Field(min_length=1, max_length=200)

    @field_validator("title")
    @classmethod
    def clean_title(cls, value: str) -> str:
        value = value.strip()
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("Chapter title must be a single nonblank line")
        return value


class ImportCommit(BaseModel):
    preview_token: uuid.UUID
    commit_key: uuid.UUID
    chapters: list[ChapterMapping] = Field(min_length=1, max_length=100)
    enrich_with_ai: bool = False


class ImportedChapter(BaseModel):
    id: uuid.UUID
    title: str
    paragraph_count: int


class ImportResult(BaseModel):
    chapters: list[ImportedChapter]
    paragraph_count: int
    ai_enrichment_requested: bool
