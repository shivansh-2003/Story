import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TurnRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    sequence: int
    content: str
    instruction: str | None
    scene_id: uuid.UUID | None = None
    version: int
    source: str
    updated_at: datetime


class TurnUpdate(BaseModel):
    content: str = Field(min_length=1, max_length=50000)
    expected_version: int = Field(ge=1)

    @field_validator("content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Paragraph must not be blank")
        return value


class RestoreRequest(BaseModel):
    revision_id: uuid.UUID
    expected_version: int = Field(ge=1)


class RevisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    revision_number: int
    content: str
    source: str
    restored_from: int | None
    created_at: datetime
