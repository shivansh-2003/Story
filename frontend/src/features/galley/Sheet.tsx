import type { Turn } from "@/lib/types";
import styles from "@/styles/galley.module.css";
import { Paragraph } from "./Paragraph";
import { PendingDraft } from "./PendingDraft";
import { DraftActions } from "./DraftActions";

export function Sheet({
  paragraphs,
  justAcceptedIndex,
  pendingTurn,
  streaming,
  editing,
  busy,
  onManualEdit,
  onEditSave,
  onEditCancel,
  onKeep,
  onRewrite,
  onEdit,
  onDiscard,
}: {
  paragraphs: string[];
  justAcceptedIndex: number | null;
  pendingTurn: Turn | null;
  streaming: boolean;
  editing: boolean;
  busy: boolean;
  onManualEdit: (content: string) => void;
  onEditSave: (content: string) => void;
  onEditCancel: () => void;
  onKeep: () => void;
  onRewrite: (instruction: string) => void;
  onEdit: () => void;
  onDiscard: () => void;
}) {
  const empty = paragraphs.length === 0 && !pendingTurn;

  return (
    <div className={styles.sheet}>
      {empty && (
        <p className="font-manuscript text-[1.1875rem] italic text-muted-foreground">
          The page is blank. Tell it what happens first.
        </p>
      )}
      {paragraphs.map((text, i) => (
        <Paragraph key={i} index={i} text={text} justAccepted={i === justAcceptedIndex} />
      ))}
      {pendingTurn && (
        <div>
          <PendingDraft
            index={paragraphs.length}
            content={pendingTurn.content}
            streaming={streaming}
            editing={editing}
            onManualEdit={onManualEdit}
            onEditSave={onEditSave}
            onEditCancel={onEditCancel}
          />
          {!editing && !streaming && (
            <DraftActions disabled={busy} onKeep={onKeep} onRewrite={onRewrite} onEdit={onEdit} onDiscard={onDiscard} />
          )}
        </div>
      )}
    </div>
  );
}
