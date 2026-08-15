import { apiFetch } from "@/lib/apiFetch";
import type { Chapter, ChapterDetail, ChapterStatus, Character, UUID } from "@/lib/types";

export type ChapterInput = {
  title?: string | null;
  target_length_words?: number | null;
};

export type ChapterUpdateInput = ChapterInput & {
  status?: ChapterStatus;
  summary?: string | null;
};

export const listChapters = (storyId: UUID, signal?: AbortSignal) =>
  apiFetch<Chapter[]>(`/stories/${storyId}/chapters`, { signal });

export const createChapter = (storyId: UUID, body: ChapterInput) =>
  apiFetch<Chapter>(`/stories/${storyId}/chapters`, { method: "POST", body });

export const getChapter = (storyId: UUID, chapterId: UUID) =>
  apiFetch<ChapterDetail>(`/stories/${storyId}/chapters/${chapterId}`);

export const updateChapter = (storyId: UUID, chapterId: UUID, body: ChapterUpdateInput) =>
  apiFetch<Chapter>(`/stories/${storyId}/chapters/${chapterId}`, { method: "PATCH", body });

export const archiveChapter = (storyId: UUID, chapterId: UUID) =>
  apiFetch<void>(`/stories/${storyId}/chapters/${chapterId}`, { method: "DELETE" });

export const reorderChapters = (storyId: UUID, items: { chapter_id: UUID; order_index: number }[]) =>
  apiFetch<void>(`/stories/${storyId}/chapters/reorder`, { method: "PATCH", body: { items } });

export const addActiveCharacter = (storyId: UUID, chapterId: UUID, characterId: UUID) =>
  apiFetch<void>(`/stories/${storyId}/chapters/${chapterId}/characters`, {
    method: "POST",
    query: { character_id: characterId },
  });

export type NewCharacterInput = {
  name: string;
  role?: string | null;
  motivation?: string | null;
  backstory?: string | null;
};

// Creates the character AND activates it in this chapter in one call —
// so the frontend doesn't sequence a create + an activate request.
export const createAndActivateCharacter = (storyId: UUID, chapterId: UUID, body: NewCharacterInput) =>
  apiFetch<Character>(`/stories/${storyId}/chapters/${chapterId}/characters/new`, { method: "POST", body });

export const removeActiveCharacter = (storyId: UUID, chapterId: UUID, characterId: UUID) =>
  apiFetch<void>(`/stories/${storyId}/chapters/${chapterId}/characters/${characterId}`, { method: "DELETE" });
