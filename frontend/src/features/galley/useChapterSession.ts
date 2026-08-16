import { useCallback, useEffect, useRef, useState } from "react";
import { useStreamBuffer } from "@/hooks/useStreamBuffer";
import type { ChapterDetail, Turn, UUID } from "@/lib/types";
import * as api from "./generationApi";

type Status = "idle" | "generating" | "accepting" | "completing" | "error";
type Length = "short" | "standard" | "long";

type ChapterSessionState = {
  acceptedParagraphs: string[]; // mirrors ChapterTurn rows, seeded on load
  pendingTurn: Turn | null; // mirrors Redis pending_turn
  siblingAttempts: Turn[]; // mirrors Redis sibling_attempts, display-only
  status: Status;
  errorMessage: string | null;
};

const initialState: ChapterSessionState = {
  acceptedParagraphs: [],
  pendingTurn: null,
  siblingAttempts: [],
  status: "idle",
  errorMessage: null,
};

export function useChapterSession(storyId: UUID, chapterId: UUID) {
  const [state, setState] = useState<ChapterSessionState>(initialState);
  const stream = useStreamBuffer();
  const abortRef = useRef<AbortController | null>(null);

  // rAF-batched: stream.text only changes once per frame no matter how many
  // deltas arrived in between, so this setState runs at frame rate, not
  // token rate.
  useEffect(() => {
    if (state.status !== "generating") return;
    setState((s) => (s.pendingTurn ? { ...s, pendingTurn: { ...s.pendingTurn, content: stream.text } } : s));
  }, [stream.text, state.status]);

  // Seeded from GalleyPage's own react-query fetch — this hook used to fetch
  // getChapter() a second time itself, doubling the request (and the three
  // sequential DB round trips behind it) on every chapter open.
  const hydrate = useCallback((data: ChapterDetail) => {
    setState((s) => ({ ...s, acceptedParagraphs: data.body ? data.body.split("\n\n") : [] }));
    // pendingTurn intentionally NOT restored from a full page reload — there's
    // no GET .../session endpoint exposing Redis state. Known gap, see GalleyPage.
  }, []);

  const runStream = useCallback(
    async (instruction: string, streamFn: (signal: AbortSignal) => Promise<void>) => {
      stream.reset();
      const controller = new AbortController();
      abortRef.current = controller;
      setState((s) => ({
        ...s,
        status: "generating",
        errorMessage: null,
        siblingAttempts: s.pendingTurn ? [s.pendingTurn, ...s.siblingAttempts].slice(0, 3) : s.siblingAttempts,
        pendingTurn: { content: "", instruction, source: "ai" },
      }));
      try {
        await streamFn(controller.signal);
        // peek(), not .text — the last delta may not have hit a rAF flush yet.
        setState((s) => (s.pendingTurn ? { ...s, status: "idle", pendingTurn: { ...s.pendingTurn, content: stream.peek() } } : { ...s, status: "idle" }));
      } catch (e) {
        if ((e as Error).name === "AbortError") {
          setState((s) => ({ ...s, status: "idle" }));
        } else {
          setState((s) => ({ ...s, status: "error", errorMessage: (e as Error).message, pendingTurn: null }));
        }
      } finally {
        abortRef.current = null;
      }
    },
    [stream],
  );

  const doGenerate = useCallback(
    (instruction: string, length: Length) =>
      runStream(instruction, (signal) => api.generate(storyId, chapterId, instruction, length, stream.append, signal)),
    [storyId, chapterId, runStream, stream.append],
  );

  const doEditInstruction = useCallback(
    (instruction: string) =>
      runStream(instruction, (signal) => api.generateEdit(storyId, chapterId, instruction, stream.append, signal)),
    [storyId, chapterId, runStream, stream.append],
  );

  const stopGenerating = useCallback(() => {
    abortRef.current?.abort();
  }, []);

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
    setState((s) => ({ ...s, pendingTurn: null, siblingAttempts: [] }));
  }, [storyId, chapterId]);

  const restoreSibling = useCallback((turn: Turn) => {
    // local-only swap — no server call needed just to preview a sibling.
    // If the user then accepts, that accept call is what makes it durable.
    setState((s) => ({ ...s, pendingTurn: turn, siblingAttempts: s.siblingAttempts.filter((t) => t !== turn) }));
  }, []);

  const doComplete = useCallback(async () => {
    if (state.pendingTurn) {
      setState((s) => ({ ...s, errorMessage: "Resolve the draft on the page first — keep it or throw it away." }));
      return false; // mirrors the backend's explicit block
    }
    setState((s) => ({ ...s, status: "completing" }));
    try {
      await api.completeChapter(storyId, chapterId);
      setState((s) => ({ ...s, status: "idle" }));
      return true;
    } catch (e) {
      setState((s) => ({ ...s, status: "error", errorMessage: (e as Error).message }));
      return false;
    }
  }, [storyId, chapterId, state.pendingTurn]);

  return {
    state,
    hydrate,
    doGenerate,
    doEditInstruction,
    doManualEdit,
    doAccept,
    doDiscard,
    restoreSibling,
    doComplete,
    stopGenerating,
  };
}
