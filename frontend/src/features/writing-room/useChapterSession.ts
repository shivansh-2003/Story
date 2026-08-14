import { useCallback, useState } from "react";
import { getChapter } from "@/features/chapters/chaptersApi";
import type { Turn, UUID } from "@/lib/types";
import * as api from "./generationApi";

type Status = "idle" | "generating" | "accepting" | "completing" | "error";

type ChapterSessionState = {
  acceptedParagraphs: string[]; // mirrors ChapterTurn rows, seeded on load
  chapterStatus: string | null;
  pendingTurn: Turn | null; // mirrors Redis pending_turn
  siblingAttempts: Turn[]; // mirrors Redis sibling_attempts, display-only
  status: Status;
  errorMessage: string | null;
};

const initialState: ChapterSessionState = {
  acceptedParagraphs: [],
  chapterStatus: null,
  pendingTurn: null,
  siblingAttempts: [],
  status: "idle",
  errorMessage: null,
};

export function useChapterSession(storyId: UUID, chapterId: UUID) {
  const [state, setState] = useState<ChapterSessionState>(initialState);

  const loadChapter = useCallback(async () => {
    const data = await getChapter(storyId, chapterId);
    setState((s) => ({
      ...s,
      acceptedParagraphs: data.body ? data.body.split("\n\n") : [],
      chapterStatus: data.status,
    }));
    // pendingTurn intentionally NOT restored from a full page reload — there's
    // no GET .../session endpoint exposing Redis state. Known gap, see WritingRoom.
  }, [storyId, chapterId]);

  // Both stream: the pending draft appears empty, then grows word-by-word as
  // SSE chunks arrive, instead of popping in all at once after a multi-second
  // wait. The accumulated text IS what lands in Redis (server does the same
  // concatenation) — no follow-up fetch needed once the stream reports done.
  const doGenerate = useCallback(
    async (instruction: string, length: "short" | "standard" | "long") => {
      setState((s) => ({
        ...s,
        status: "generating",
        errorMessage: null,
        siblingAttempts: s.pendingTurn ? [s.pendingTurn, ...s.siblingAttempts].slice(0, 3) : s.siblingAttempts,
        pendingTurn: { content: "", instruction, source: "ai" },
      }));
      try {
        await api.generate(storyId, chapterId, instruction, length, (delta) => {
          setState((s) => ({
            ...s,
            pendingTurn: s.pendingTurn ? { ...s.pendingTurn, content: s.pendingTurn.content + delta } : s.pendingTurn,
          }));
        });
        setState((s) => ({ ...s, status: "idle" }));
      } catch (e) {
        setState((s) => ({ ...s, status: "error", errorMessage: (e as Error).message, pendingTurn: null }));
      }
    },
    [storyId, chapterId],
  );

  const doEditInstruction = useCallback(
    async (instruction: string) => {
      setState((s) => ({
        ...s,
        status: "generating",
        errorMessage: null,
        siblingAttempts: s.pendingTurn ? [s.pendingTurn, ...s.siblingAttempts].slice(0, 3) : s.siblingAttempts,
        pendingTurn: { content: "", instruction, source: "ai" },
      }));
      try {
        await api.generateEdit(storyId, chapterId, instruction, (delta) => {
          setState((s) => ({
            ...s,
            pendingTurn: s.pendingTurn ? { ...s.pendingTurn, content: s.pendingTurn.content + delta } : s.pendingTurn,
          }));
        });
        setState((s) => ({ ...s, status: "idle" }));
      } catch (e) {
        setState((s) => ({ ...s, status: "error", errorMessage: (e as Error).message, pendingTurn: null }));
      }
    },
    [storyId, chapterId],
  );

  // Local-first for responsiveness; server write is debounced (useDebouncedManualEdit)
  const doManualEdit = useCallback((content: string) => {
    setState((s) => ({ ...s, pendingTurn: { content, instruction: null, source: "user_edit" } }));
  }, []);

  const doAccept = useCallback(async () => {
    if (!state.pendingTurn) return;
    setState((s) => ({ ...s, status: "accepting" }));
    const accepted = state.pendingTurn.content;
    try {
      await api.accept(storyId, chapterId);
      setState((s) => ({
        ...s,
        status: "idle",
        acceptedParagraphs: [...s.acceptedParagraphs, accepted],
        pendingTurn: null,
        siblingAttempts: [],
      }));
    } catch (e) {
      setState((s) => ({ ...s, status: "error", errorMessage: (e as Error).message }));
    }
  }, [storyId, chapterId, state.pendingTurn]);

  const doDiscard = useCallback(async () => {
    await api.discard(storyId, chapterId);
    setState((s) => ({ ...s, pendingTurn: null }));
  }, [storyId, chapterId]);

  const restoreSibling = useCallback((turn: Turn) => {
    // local-only swap — no server call needed just to preview a sibling.
    // If the user then accepts, that accept call is what makes it durable.
    setState((s) => ({ ...s, pendingTurn: turn, siblingAttempts: s.siblingAttempts.filter((t) => t !== turn) }));
  }, []);

  const doComplete = useCallback(async () => {
    if (state.pendingTurn) {
      setState((s) => ({ ...s, errorMessage: "Resolve the current draft before completing the chapter." }));
      return; // mirrors the backend's explicit block
    }
    setState((s) => ({ ...s, status: "completing" }));
    try {
      await api.completeChapter(storyId, chapterId);
      setState((s) => ({ ...s, status: "idle", chapterStatus: "complete" }));
    } catch (e) {
      setState((s) => ({ ...s, status: "error", errorMessage: (e as Error).message }));
    }
  }, [storyId, chapterId, state.pendingTurn]);

  return { state, loadChapter, doGenerate, doEditInstruction, doManualEdit, doAccept, doDiscard, restoreSibling, doComplete };
}
