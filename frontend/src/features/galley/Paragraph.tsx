import { useEffect, useRef } from "react";
import styles from "@/styles/galley.module.css";
import { inkSettle } from "./inkSettle";
import { paragraphSelection } from "@/features/rewriting/selection";
import type { TextSelection } from "@/features/rewriting/rewritingApi";

export function Paragraph({ index, text, justAccepted, onSelection }: { index: number; text: string; justAccepted: boolean; onSelection?: (selection: TextSelection | null) => void }) {
  const ref = useRef<HTMLParagraphElement>(null);
  const contentRef = useRef<HTMLSpanElement>(null);
  function captureSelection() {
    if (contentRef.current && onSelection) onSelection(paragraphSelection(contentRef.current, text));
  }

  useEffect(() => {
    if (justAccepted && ref.current) {
      ref.current.dataset.state = "pending";
      inkSettle(ref.current, () => {});
    }
  }, [justAccepted]);

  return (
    <p ref={ref} className={styles.paragraph} data-state={justAccepted ? "pending" : "ink"} onMouseUp={captureSelection} onKeyUp={captureSelection}>
      <span className={styles.gutterMark} aria-hidden="true">
        {String(index + 1).padStart(2, "0")}
        <br />
        <span className={styles.gutterTick} data-gutter-tick style={justAccepted ? { opacity: 0 } : undefined} />
      </span>
      <span ref={contentRef}>{text}</span>
    </p>
  );
}
