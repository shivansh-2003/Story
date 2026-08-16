import { apiFetch, apiStream } from "@/lib/apiFetch";
import type { Turn, UUID } from "@/lib/types";

// Adapted from the generation-module frontend guide: the actual backend
// nests generation routes under /stories/{storyId}/chapters/{chapterId}/...
// (not the flat /chapters/{id}/... the guide assumed), so story_id comes
// from the URL, not the request body — matches GenerateRequest/EditRequest
// in app/generation/schemas.py exactly.

const base = (storyId: UUID, chapterId: UUID) => `/stories/${storyId}/chapters/${chapterId}`;

// generate/generateEdit stream via SSE — app/generation/router.py returns
// text/event-stream, not a single TurnOut body, so these resolve to void and
// report progress through onDelta instead of a return value.

export const generate = (
  storyId: UUID,
  chapterId: UUID,
  instruction: string,
  length: "short" | "standard" | "long",
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
) => apiStream(`${base(storyId, chapterId)}/generate`, { instruction, length }, onDelta, signal);

export const generateEdit = (
  storyId: UUID,
  chapterId: UUID,
  instruction: string,
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
) => apiStream(`${base(storyId, chapterId)}/generate/edit`, { instruction }, onDelta, signal);

export const manualEdit = (storyId: UUID, chapterId: UUID, content: string) =>
  apiFetch<Turn>(`${base(storyId, chapterId)}/manual-edit`, { method: "POST", body: { content } });

export const accept = (storyId: UUID, chapterId: UUID) =>
  apiFetch<{ accepted: boolean; sequence: number }>(`${base(storyId, chapterId)}/accept`, { method: "POST" });

export const discard = (storyId: UUID, chapterId: UUID) =>
  apiFetch<{ discarded: boolean }>(`${base(storyId, chapterId)}/discard`, { method: "POST" });

export const completeChapter = (storyId: UUID, chapterId: UUID) =>
  apiFetch<{ status: string; summarizing: boolean }>(`${base(storyId, chapterId)}/complete`, { method: "POST" });
