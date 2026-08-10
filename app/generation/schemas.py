from typing import Literal

from pydantic import BaseModel


class GenerateRequest(BaseModel):
    instruction: str
    length: Literal["short", "standard", "long"] = "standard"


class EditRequest(BaseModel):
    instruction: str


class ManualEditRequest(BaseModel):
    content: str


class TurnOut(BaseModel):
    content: str
    instruction: str | None
    source: Literal["ai", "user_edit"]
