import { apiFetch, apiStream } from "@/lib/apiFetch";
import type {
  AcceptedTurn,
  ChapterSession,
  Turn,
  TurnRevision,
  UUID,
} from "@/lib/types";

// Adapted from the generation-module frontend guide: the actual backend
// nests generation routes under /stories/{storyId}/chapters/{chapterId}/...
// (not the flat /chapters/{id}/... the guide assumed), so story_id comes
// from the URL, not the request body — matches GenerateRequest/EditRequest
// in app/generation/schemas.py exactly.

const base = (storyId: UUID, chapterId: UUID) =>
  `/stories/${storyId}/chapters/${chapterId}`;

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
  scene_id?: UUID | null,
) =>
  apiStream(
    `${base(storyId, chapterId)}/generate`,
    { instruction, length, scene_id: scene_id ?? null },
    onDelta,
    signal,
  );

export const generateEdit = (
  storyId: UUID,
  chapterId: UUID,
  instruction: string,
  onDelta: (delta: string) => void,
  signal?: AbortSignal,
) =>
  apiStream(
    `${base(storyId, chapterId)}/generate/edit`,
    { instruction },
    onDelta,
    signal,
  );

export const manualEdit = (
  storyId: UUID,
  chapterId: UUID,
  content: string,
  expected_version?: number,
) =>
  apiFetch<Turn>(`${base(storyId, chapterId)}/manual-edit`, {
    method: "POST",
    body: { content, expected_version },
  });

export const accept = (storyId: UUID, chapterId: UUID, draft_id?: UUID) =>
  apiFetch<{ accepted: boolean; sequence: number; turn: AcceptedTurn }>(
    `${base(storyId, chapterId)}/accept`,
    { method: "POST", body: { draft_id } },
  );

export const getSession = (
  storyId: UUID,
  chapterId: UUID,
  signal?: AbortSignal,
) =>
  apiFetch<ChapterSession>(`${base(storyId, chapterId)}/session`, { signal });

export const selectAttempt = (
  storyId: UUID,
  chapterId: UUID,
  draft_id: UUID,
  expected_version: number,
) =>
  apiFetch(`${base(storyId, chapterId)}/session/select`, {
    method: "POST",
    body: { draft_id, expected_version },
  });

export const editTurn = (
  storyId: UUID,
  chapterId: UUID,
  turn: AcceptedTurn,
  content: string,
) =>
  apiFetch<AcceptedTurn>(`${base(storyId, chapterId)}/turns/${turn.id}`, {
    method: "PATCH",
    body: { content, expected_version: turn.version },
  });

export const getRevisions = (storyId: UUID, chapterId: UUID, turnId: UUID) =>
  apiFetch<TurnRevision[]>(
    `${base(storyId, chapterId)}/turns/${turnId}/revisions`,
  );

export const restoreRevision = (
  storyId: UUID,
  chapterId: UUID,
  turn: AcceptedTurn,
  revision_id: UUID,
) =>
  apiFetch<AcceptedTurn>(
    `${base(storyId, chapterId)}/turns/${turn.id}/restore`,
    { method: "POST", body: { revision_id, expected_version: turn.version } },
  );

export type MemoryStatus = {
  revision: number;
  fresh: boolean;
  status: string;
  error: string | null;
};
export const getMemoryStatus = (storyId: UUID, chapterId: UUID) =>
  apiFetch<MemoryStatus>(`${base(storyId, chapterId)}/memory-status`);
export const refreshMemory = (storyId: UUID, chapterId: UUID) =>
  apiFetch(`${base(storyId, chapterId)}/memory-refresh`, { method: "POST" });

export const discard = (storyId: UUID, chapterId: UUID) =>
  apiFetch<{ discarded: boolean }>(`${base(storyId, chapterId)}/discard`, {
    method: "POST",
  });

export const completeChapter = (storyId: UUID, chapterId: UUID) =>
  apiFetch<{ status: string; summarizing: boolean }>(
    `${base(storyId, chapterId)}/complete`,
    { method: "POST" },
  );
