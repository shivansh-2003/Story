import uuid
from typing import Literal

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    instruction: str
    length: Literal["short", "standard", "long"] = "standard"
    scene_id: uuid.UUID | None = None


class EditRequest(BaseModel):
    instruction: str


class ManualEditRequest(BaseModel):
    content: str
    expected_version: int | None = None


class AcceptRequest(BaseModel):
    draft_id: uuid.UUID | None = None


class SelectAttemptRequest(BaseModel):
    draft_id: uuid.UUID
    expected_version: int


class TurnOut(BaseModel):
    content: str
    instruction: str | None
    source: Literal["ai", "user_edit"]
