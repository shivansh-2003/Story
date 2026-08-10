import { apiFetch } from "@/lib/apiFetch";
import type { Chapter, ChapterDetail, ChapterStatus, UUID } from "@/lib/types";

export type ChapterInput = {
  title?: string | null;
  target_length_words?: number | null;
};

export type ChapterUpdateInput = ChapterInput & {
  status?: ChapterStatus;
  summary?: string | null;
};

export const listChapters = (storyId: UUID) => apiFetch<Chapter[]>(`/stories/${storyId}/chapters`);

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

export const removeActiveCharacter = (storyId: UUID, chapterId: UUID, characterId: UUID) =>
  apiFetch<void>(`/stories/${storyId}/chapters/${chapterId}/characters/${characterId}`, { method: "DELETE" });
