import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


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
