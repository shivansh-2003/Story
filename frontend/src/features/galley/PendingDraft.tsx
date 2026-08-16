import { useEffect, useRef, useState, type FocusEvent, type KeyboardEvent } from "react";
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
  onManualEdit,
  onEditSave,
  onEditCancel,
}: {
  index: number;
  content: string;
  streaming: boolean;
  editing: boolean;
  onManualEdit: (content: string) => void;
  onEditSave: (content: string) => void;
  onEditCancel: () => void;
}) {
  const editableRef = useRef<HTMLParagraphElement>(null);
  const caretScope = useAnimeScope(() => {
    if (prefersReducedMotion()) return;
    animate("[data-caret]", { opacity: [1, 0.2], duration: 900, alternate: true, loop: true });
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
    if (editing && editableRef.current) {
      editableRef.current.focus();
      const range = document.createRange();
      range.selectNodeContents(editableRef.current);
      range.collapse(false);
      const sel = window.getSelection();
      sel?.removeAllRanges();
      sel?.addRange(range);
    }
  }, [editing]);

  function handleBlur(e: FocusEvent<HTMLParagraphElement>) {
    if (!editing) return;
    onEditSave(e.currentTarget.textContent ?? "");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLParagraphElement>) {
    if (!editing) return;
    if (e.key === "Escape") {
      e.preventDefault();
      onEditCancel();
    } else if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      e.currentTarget.blur();
    }
  }

  return (
    <div ref={caretScope} className={styles.pendingWash} role="group" aria-label="draft, not yet kept">
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {srMessage}
      </span>
      <p
        ref={editableRef}
        className={styles.paragraph}
        data-state="pending"
        style={editing ? { color: "rgb(var(--sheet-foreground))", fontStyle: "normal" } : undefined}
        contentEditable={editing}
        suppressContentEditableWarning
        onBlur={handleBlur}
        onKeyDown={handleKeyDown}
        onInput={(e) => editing && onManualEdit(e.currentTarget.textContent ?? "")}
      >
        <span className={`${styles.gutterMark} ${styles.pendingMark}`} aria-hidden="true">
          ◆
        </span>
        {editing ? content : content || " "}
        {streaming && !editing && <span className={styles.caret} data-caret />}
      </p>
      {!editing && (
        <p className="mt-1 font-mono text-[0.6875rem] uppercase tracking-wide text-muted-foreground">
          draft {index + 1} — {wordCount(content)} words
        </p>
      )}
    </div>
  );
}
