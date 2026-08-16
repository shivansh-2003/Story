import { useCallback, useRef } from "react";
import type { UUID } from "@/lib/types";
import * as api from "./generationApi";

export function useDebouncedManualEdit(storyId: UUID, chapterId: UUID, onSynced: (content: string) => void) {
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);

  return useCallback(
    (content: string) => {
      onSynced(content); // update local UI immediately, no lag
      clearTimeout(timer.current);
      timer.current = setTimeout(() => {
        api.manualEdit(storyId, chapterId, content).catch(() => {
          // ponytail: silent fail + next debounced write retries with fresh
          // content. Add a visible "not saved" indicator only if this proves
          // to actually confuse users in practice.
        });
      }, 600);
    },
    [storyId, chapterId, onSynced],
  );
}
