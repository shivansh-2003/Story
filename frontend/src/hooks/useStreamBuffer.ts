import { useCallback, useRef, useSyncExternalStore } from "react";

// Per-delta setState at token speed thrashes React 19's scheduler — this
// accumulates deltas into a plain string and only notifies subscribers once
// per animation frame, however many deltas arrived in between.
function createStreamStore() {
  let text = "";
  let rafId: number | null = null;
  const listeners = new Set<() => void>();

  function flush() {
    rafId = null;
    listeners.forEach((l) => l());
  }

  return {
    append(delta: string) {
      text += delta;
      if (rafId === null) rafId = requestAnimationFrame(flush);
    },
    reset() {
      text = "";
      if (rafId !== null) {
        cancelAnimationFrame(rafId);
        rafId = null;
      }
      listeners.forEach((l) => l());
    },
    getSnapshot() {
      return text;
    },
    subscribe(listener: () => void) {
      listeners.add(listener);
      return () => listeners.delete(listener);
    },
  };
}

export function useStreamBuffer() {
  const storeRef = useRef<ReturnType<typeof createStreamStore> | null>(null);
  if (!storeRef.current) storeRef.current = createStreamStore();
  const store = storeRef.current;

  const text = useSyncExternalStore(store.subscribe, store.getSnapshot);
  const append = useCallback((delta: string) => store.append(delta), [store]);
  const reset = useCallback(() => store.reset(), [store]);
  // The rendered `text` lags by up to one animation frame. When a caller
  // needs the true latest value synchronously (e.g. right as a stream ends,
  // before the final rAF flush fires), read the store directly instead.
  const peek = useCallback(() => store.getSnapshot(), [store]);

  return { text, append, reset, peek };
}
