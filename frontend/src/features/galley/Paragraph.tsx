import { useEffect, useRef } from "react";
import styles from "@/styles/galley.module.css";
import { inkSettle } from "./inkSettle";

export function Paragraph({ index, text, justAccepted }: { index: number; text: string; justAccepted: boolean }) {
  const ref = useRef<HTMLParagraphElement>(null);

  useEffect(() => {
    if (justAccepted && ref.current) {
      ref.current.dataset.state = "pending";
      inkSettle(ref.current, () => {});
    }
  }, [justAccepted]);

  return (
    <p ref={ref} className={styles.paragraph} data-state={justAccepted ? "pending" : "ink"}>
      <span className={styles.gutterMark} aria-hidden="true">
        {String(index + 1).padStart(2, "0")}
        <br />
        <span className={styles.gutterTick} data-gutter-tick style={justAccepted ? { opacity: 0 } : undefined} />
      </span>
      {text}
    </p>
  );
}
