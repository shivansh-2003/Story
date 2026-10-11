import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { animate } from "animejs";
import { useAnimeScope } from "@/hooks/useAnimeScope";
import { prefersReducedMotion } from "@/lib/motion";
import styles from "@/styles/galley.module.css";

function wordCount(text: string): number {
  const trimmed = text.trim();
  return trimmed ? trimmed.split(/\s+/).length : 0;
}

// Announcing every delta would machine-gun a screen reader at token speed —
// only the newest *complete* sentence gets spoken while streaming.
function lastCompleteSentence(text: string): string | null {
  const matches = text.match(/[^.!?]*[.!?]+/g);
  return matches?.length ? matches[matches.length - 1].trim() : null;
}

export function PendingDraft({
  index,
  content,
  streaming,
  editing,
  busy,
  onEditSave,
  onEditCancel,
}: {
  index: number;
  content: string;
  streaming: boolean;
  editing: boolean;
  busy: boolean;
  onEditSave: (content: string) => void;
  onEditCancel: () => void;
}) {
  const editableRef = useRef<HTMLTextAreaElement>(null);
  const [draft, setDraft] = useState(content);
  const caretScope = useAnimeScope(() => {
    if (prefersReducedMotion()) return;
    animate("[data-caret]", {
      opacity: [1, 0.2],
      duration: 900,
      alternate: true,
      loop: true,
    });
  }, [streaming]);

  // Screen-reader announcements: throttled to sentence boundaries while
  // streaming, then a single "draft ready" summary when it stops.
  const [srMessage, setSrMessage] = useState("");
  const lastAnnounced = useRef("");
  const wasStreaming = useRef(streaming);
  useEffect(() => {
    if (streaming) {
      const sentence = lastCompleteSentence(content);
      if (sentence && sentence !== lastAnnounced.current) {
        lastAnnounced.current = sentence;
        setSrMessage(sentence);
      }
    } else if (wasStreaming.current) {
      setSrMessage(`Draft ready, ${wordCount(content)} words.`);
      lastAnnounced.current = "";
    }
    wasStreaming.current = streaming;
  }, [content, streaming]);

  useEffect(() => {
    if (editing) {
      setDraft(content);
      editableRef.current?.focus();
    }
  }, [editing, content]);

  function handleKeyDown(e: KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Escape") {
      e.preventDefault();
      e.stopPropagation();
      if (!busy) onEditCancel();
    } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      e.stopPropagation();
      if (!busy && draft.trim()) onEditSave(draft);
    }
  }

  return (
    <div
      ref={caretScope}
      className={styles.pendingWash}
      role="group"
      aria-label="draft, not yet kept"
    >
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {srMessage}
      </span>
      {editing ? (
        <div>
          <label
            htmlFor="pending-paragraph"
            className="text-sm"
            style={{ color: "rgb(var(--sheet-foreground))" }}
          >
            Edit pending paragraph
          </label>
          <textarea
            id="pending-paragraph"
            ref={editableRef}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={handleKeyDown}
            disabled={busy}
            maxLength={50000}
            className="mt-2 min-h-40 w-full rounded border p-3 font-manuscript text-lg"
            style={{
              color: "rgb(var(--sheet-foreground))",
              background: "rgb(var(--sheet))",
            }}
          />
          <div
            className="mt-2 flex gap-4 text-sm"
            style={{ color: "rgb(var(--pending))" }}
          >
            <button
              disabled={busy || !draft.trim()}
              onClick={() => onEditSave(draft)}
            >
              {busy ? "Saving…" : "Save draft"}
            </button>
            <button disabled={busy} onClick={onEditCancel}>
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <p className={styles.paragraph} data-state="pending">
          <span
            className={`${styles.gutterMark} ${styles.pendingMark}`}
            aria-hidden="true"
          >
            ◆
          </span>
          {content || " "}
          {streaming && <span className={styles.caret} data-caret />}
        </p>
      )}
      {!editing && (
        <p className="mt-1 font-mono text-[0.6875rem] uppercase tracking-wide text-muted-foreground">
          draft {index + 1} — {wordCount(content)} words
        </p>
      )}
    </div>
  );
}
