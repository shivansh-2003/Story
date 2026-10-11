import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class RewriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposal_id: uuid.UUID
    expected_version: int = Field(ge=1)
    start: int = Field(ge=0, strict=True)
    end: int = Field(gt=0, strict=True)
    original_text: str = Field(min_length=1, max_length=12000)
    instruction: str = Field(min_length=1, max_length=2000)

    @field_validator("original_text", "instruction")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Text must not be blank")
        return value

    @model_validator(mode="after")
    def valid_range(self):
        if self.end <= self.start or self.end - self.start != len(self.original_text):
            raise ValueError("Selection must use Unicode code-point offsets")
        return self


class RewriteOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proposed_text: str = Field(min_length=1, max_length=16000)

    @field_validator("proposed_text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Replacement must not be blank")
        return value


class ProposalRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    turn_id: uuid.UUID
    base_turn_version: int
    base_manuscript_revision: int
    context_version: str
    start: int
    end: int
    original_text: str
    proposed_text: str | None
    instruction: str
    status: str
    applied_version: int | None
    created_at: datetime
    expires_at: datetime

    @field_validator("created_at", "expires_at")
    @classmethod
    def utc_timestamps(cls, value):
        # SQLite returns naive timestamps; persisted proposal times are UTC.
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value


class ApplyRead(BaseModel):
    proposal_id: uuid.UUID
    applied_version: int
    applied_content: str
    already_applied: bool
