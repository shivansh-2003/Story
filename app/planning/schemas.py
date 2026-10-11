import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PlanFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    objective: str = Field(default="", max_length=2000)
    conflict: str = Field(default="", max_length=2000)
    ending_beat: str = Field(default="", max_length=2000)
    notes: str = Field(default="", max_length=2000)


class PlanUpdate(PlanFields):
    expected_version: int = Field(ge=0)


class PlanRead(PlanFields):
    chapter_id: uuid.UUID
    version: int
    planning_revision: int


class SceneFields(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=200)
    goal: str = Field(default="", max_length=1000)
    conflict: str = Field(default="", max_length=1000)
    outcome: str = Field(default="", max_length=1000)
    setting: str = Field(default="", max_length=1000)
    notes: str = Field(default="", max_length=1000)
    pov_character_id: uuid.UUID | None = None
    character_ids: list[uuid.UUID] = Field(default_factory=list, max_length=50)

    @field_validator("title")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Scene title must not be blank")
        return value.strip()

    @model_validator(mode="after")
    def valid_cast(self):
        if len(set(self.character_ids)) != len(self.character_ids):
            raise ValueError("Scene cast must not contain duplicates")
        if self.pov_character_id and self.pov_character_id not in self.character_ids:
            raise ValueError("The POV character must be included in the scene cast")
        return self


class SceneUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1)
    title: str | None = Field(default=None, max_length=200)
    goal: str | None = Field(default=None, max_length=1000)
    conflict: str | None = Field(default=None, max_length=1000)
    outcome: str | None = Field(default=None, max_length=1000)
    setting: str | None = Field(default=None, max_length=1000)
    notes: str | None = Field(default=None, max_length=1000)
    pov_character_id: uuid.UUID | None = None
    character_ids: list[uuid.UUID] | None = Field(default=None, max_length=50)


class SceneRead(SceneFields):
    id: uuid.UUID
    chapter_id: uuid.UUID
    order_index: int
    version: int
    updated_at: datetime


class SceneReorder(BaseModel):
    scene_ids: list[uuid.UUID] = Field(max_length=100)
    expected_planning_revision: int = Field(ge=0)


class SuggestionRequest(BaseModel):
    chapter_id: uuid.UUID
    instruction: str = Field(min_length=1, max_length=2000)


class PlanProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    plan: PlanFields
    scenes: list[SceneFields] = Field(default_factory=list, max_length=8)


class ProposalRead(PlanProposal):
    chapter_id: uuid.UUID
    expected_plan_version: int
    expected_planning_revision: int
    expected_manuscript_revision: int


class ProposalSave(PlanProposal):
    expected_plan_version: int = Field(ge=0)
    expected_planning_revision: int = Field(ge=0)
    expected_manuscript_revision: int = Field(ge=0)
