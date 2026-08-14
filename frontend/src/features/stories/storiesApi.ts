import { apiFetch } from "@/lib/apiFetch";
import type { POV, Story, StoryDetail, StoryStatus, Tense, UUID } from "@/lib/types";

export type StoryInput = {
  title: string;
  genre?: string[] | null;
  tone?: string | null;
  pov?: POV | null;
  tense?: Tense | null;
  rating?: string | null;
  premise?: string | null;
  opening_line?: string | null;
  setting?: string | null;
  themes?: string[] | null;
  content_boundaries?: string | null;
  writing_style_notes?: string | null;
  target_audience?: string | null;
  status?: StoryStatus;
};

export const listStories = () => apiFetch<Story[]>("/stories");

export const createStory = (body: StoryInput) => apiFetch<Story>("/stories", { method: "POST", body });

export const getStory = (id: UUID) => apiFetch<StoryDetail>(`/stories/${id}`);

export const updateStory = (id: UUID, body: Partial<StoryInput>) =>
  apiFetch<Story>(`/stories/${id}`, { method: "PATCH", body });

export const archiveStory = (id: UUID) => apiFetch<void>(`/stories/${id}`, { method: "DELETE" });

export const importCharacterToStory = (storyId: UUID, characterId: UUID) =>
  apiFetch<void>(`/stories/${storyId}/characters`, { method: "POST", query: { character_id: characterId } });

export const removeCharacterFromStory = (storyId: UUID, characterId: UUID) =>
  apiFetch<void>(`/stories/${storyId}/characters/${characterId}`, { method: "DELETE" });
