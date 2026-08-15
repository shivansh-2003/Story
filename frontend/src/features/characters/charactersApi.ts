import { apiFetch } from "@/lib/apiFetch";
import type { Character, CharacterRelationship, UUID } from "@/lib/types";

export type CharacterInput = {
  name: string;
  role?: string | null;
  age?: string | null;
  pronouns?: string | null;
  appearance?: string | null;
  voice_notes?: string | null;
  personality_traits?: string[] | null;
  motivation?: string | null;
  flaw?: string | null;
  backstory?: string | null;
};

export const listCharacters = (signal?: AbortSignal) => apiFetch<Character[]>("/characters", { signal });

export const createCharacter = (body: CharacterInput) =>
  apiFetch<Character>("/characters", { method: "POST", body });

export const getCharacter = (id: UUID) => apiFetch<Character>(`/characters/${id}`);

export const updateCharacter = (id: UUID, body: Partial<CharacterInput>) =>
  apiFetch<Character>(`/characters/${id}`, { method: "PATCH", body });

export const archiveCharacter = (id: UUID) => apiFetch<void>(`/characters/${id}`, { method: "DELETE" });

export const listRelationships = (id: UUID) =>
  apiFetch<CharacterRelationship[]>(`/characters/${id}/relationships`);

export const addRelationship = (id: UUID, relatedCharacterId: UUID, label?: string) =>
  apiFetch<CharacterRelationship>(`/characters/${id}/relationships`, {
    method: "POST",
    body: { related_character_id: relatedCharacterId, relationship_label: label ?? null },
  });
