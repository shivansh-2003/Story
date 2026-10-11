import { useCallback, useEffect, useRef, useState } from "react";
import { useStreamBuffer } from "@/hooks/useStreamBuffer";
import type {
  AcceptedTurn,
  ChapterDetail,
  ChapterSession,
  Turn,
  UUID,
} from "@/lib/types";
import * as api from "./generationApi";

type Status =
  "idle" | "generating" | "accepting" | "completing" | "saving" | "error";
type Length = "short" | "standard" | "long";
type State = {
  acceptedParagraphs: AcceptedTurn[];
  pendingTurn: Turn | null;
  siblingAttempts: Turn[];
  sessionVersion: number;
  staleDraft: boolean;
  ready: boolean;
  status: Status;
  errorMessage: string | null;
};
const initialState: State = {
  acceptedParagraphs: [],
  pendingTurn: null,
  siblingAttempts: [],
  sessionVersion: 0,
  staleDraft: false,
  ready: false,
  status: "idle",
  errorMessage: null,
};

export function useChapterSession(storyId: UUID, chapterId: UUID) {
  const [state, setState] = useState<State>(initialState);
  const stream = useStreamBuffer();
  const abortRef = useRef<AbortController | null>(null);
  const applySession = useCallback((session: ChapterSession) => {
    setState((s) => ({
      ...s,
      pendingTurn: session.pending_turn,
      siblingAttempts: session.sibling_attempts,
      sessionVersion: session.version,
      staleDraft: session.stale_draft,
      ready: true,
    }));
  }, []);
  const reloadSession = useCallback(
    async () => applySession(await api.getSession(storyId, chapterId)),
    [storyId, chapterId, applySession],
  );

  useEffect(() => {
    const controller = new AbortController();
    setState(initialState);
    api
      .getSession(storyId, chapterId, controller.signal)
      .then(applySession)
      .catch((e: Error) => {
        if (e.name !== "AbortError")
          setState((s) => ({ ...s, status: "error", errorMessage: e.message }));
      });
    return () => {
      controller.abort();
      abortRef.current?.abort();
    };
  }, [storyId, chapterId, applySession]);

  useEffect(() => {
    if (state.status !== "generating") return;
    setState((s) =>
      s.pendingTurn
        ? { ...s, pendingTurn: { ...s.pendingTurn, content: stream.text } }
        : s,
    );
  }, [stream.text, state.status]);

  const hydrate = useCallback((data: ChapterDetail) => {
    setState((s) => ({ ...s, acceptedParagraphs: data.turns }));
  }, []);
  const updateAccepted = useCallback(
    (turn: AcceptedTurn) => {
      setState((s) => ({
        ...s,
        acceptedParagraphs: s.acceptedParagraphs.map((t) =>
          t.id === turn.id ? turn : t,
        ),
      }));
      void reloadSession().catch((e: Error) =>
        setState((s) => ({ ...s, errorMessage: e.message })),
      );
    },
    [reloadSession],
  );

  const runStream = useCallback(
    async (
      instruction: string,
      streamFn: (signal: AbortSignal) => Promise<void>,
    ) => {
      stream.reset();
      const controller = new AbortController();
      abortRef.current = controller;
      setState((s) => ({
        ...s,
        status: "generating",
        errorMessage: null,
        pendingTurn: { content: "", instruction, source: "ai" },
      }));
      try {
        await streamFn(controller.signal);
        await reloadSession();
        setState((s) => ({ ...s, status: "idle" }));
      } catch (e) {
        // Recover the server's last saved draft, including after cancellation.
        if (!controller.signal.aborted) await reloadSession().catch(() => {});
        setState((s) => ({
          ...s,
          ready:
            (e as Error).name !== "AbortError" && !!s.pendingTurn?.draft_id,
          status: "error",
          errorMessage:
            (e as Error).name === "AbortError"
              ? "Generation stopped. Reload the draft before continuing."
              : (e as Error).message,
        }));
      } finally {
        abortRef.current = null;
      }
    },
    [stream, reloadSession],
  );

  const doGenerate = useCallback(
    (instruction: string, length: Length, sceneId?: UUID | null) =>
      runStream(instruction, (signal) =>
        api.generate(
          storyId,
          chapterId,
          instruction,
          length,
          stream.append,
          signal,
          sceneId,
        ),
      ),
    [storyId, chapterId, runStream, stream.append],
  );
  const doEditInstruction = useCallback(
    (instruction: string) =>
      runStream(instruction, (signal) =>
        api.generateEdit(
          storyId,
          chapterId,
          instruction,
          stream.append,
          signal,
        ),
      ),
    [storyId, chapterId, runStream, stream.append],
  );
  const stopGenerating = useCallback(() => abortRef.current?.abort(), []);
  const saveManualEdit = useCallback(
    async (content: string) => {
      setState((s) => ({ ...s, status: "saving", errorMessage: null }));
      try {
        await api.manualEdit(storyId, chapterId, content, state.sessionVersion);
        await reloadSession();
        setState((s) => ({ ...s, status: "idle" }));
        return true;
      } catch (e) {
        setState((s) => ({
          ...s,
          status: "error",
          errorMessage: (e as Error).message,
        }));
        return false;
      }
    },
    [storyId, chapterId, state.sessionVersion, reloadSession],
  );

  const doAccept = useCallback(async () => {
    if (!state.pendingTurn?.draft_id) return false;
    setState((s) => ({ ...s, status: "accepting", errorMessage: null }));
    try {
      const { turn } = await api.accept(
        storyId,
        chapterId,
        state.pendingTurn.draft_id,
      );
      setState((s) => ({
        ...s,
        status: "idle",
        acceptedParagraphs: s.acceptedParagraphs.some((t) => t.id === turn.id)
          ? s.acceptedParagraphs
          : [...s.acceptedParagraphs, turn],
        pendingTurn: null,
        siblingAttempts: [],
        staleDraft: false,
      }));
      await reloadSession();
      return true;
    } catch (e) {
      setState((s) => ({
        ...s,
        status: "error",
        errorMessage: (e as Error).message,
      }));
      return false;
    }
  }, [storyId, chapterId, state.pendingTurn, reloadSession]);
  const doDiscard = useCallback(async () => {
    try {
      await api.discard(storyId, chapterId);
      await reloadSession();
      setState((s) => ({ ...s, status: "idle", errorMessage: null }));
    } catch (e) {
      setState((s) => ({
        ...s,
        status: "error",
        errorMessage: (e as Error).message,
      }));
    }
  }, [storyId, chapterId, reloadSession]);
  const restoreSibling = useCallback(
    async (turn: Turn) => {
      if (!turn.draft_id) return;
      setState((s) => ({ ...s, status: "saving" }));
      try {
        await api.selectAttempt(
          storyId,
          chapterId,
          turn.draft_id,
          state.sessionVersion,
        );
        await reloadSession();
        setState((s) => ({ ...s, status: "idle", errorMessage: null }));
      } catch (e) {
        setState((s) => ({
          ...s,
          status: "error",
          errorMessage: (e as Error).message,
        }));
      }
    },
    [storyId, chapterId, state.sessionVersion, reloadSession],
  );
  const doComplete = useCallback(async () => {
    if (state.pendingTurn) return false;
    setState((s) => ({ ...s, status: "completing" }));
    try {
      await api.completeChapter(storyId, chapterId);
      setState((s) => ({ ...s, status: "idle" }));
      return true;
    } catch (e) {
      setState((s) => ({
        ...s,
        status: "error",
        errorMessage: (e as Error).message,
      }));
      return false;
    }
  }, [storyId, chapterId, state.pendingTurn]);
  return {
    state,
    hydrate,
    updateAccepted,
    reloadSession,
    doGenerate,
    doEditInstruction,
    saveManualEdit,
    doAccept,
    doDiscard,
    restoreSibling,
    doComplete,
    stopGenerating,
  };
}
