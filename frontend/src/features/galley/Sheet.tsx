import type { AcceptedTurn, Turn, UUID } from "@/lib/types";
import styles from "@/styles/galley.module.css";
import { Paragraph } from "./Paragraph";
import { PendingDraft } from "./PendingDraft";
import { DraftActions } from "./DraftActions";
import { AcceptedParagraphEditor } from "./AcceptedParagraphEditor";
import { useState } from "react";
import { RewriteDialog } from "@/features/rewriting/RewriteDialog";
import type { TextSelection } from "@/features/rewriting/rewritingApi";

export function Sheet({
  storyId,
  chapterId,
  locked,
  onAcceptedSaved,
  paragraphs,
  sceneTitles = {},
  justAcceptedIndex,
  pendingTurn,
  streaming,
  editing,
  busy,
  onEditSave,
  onEditCancel,
  onKeep,
  onRewrite,
  onEdit,
  onDiscard,
}: {
  storyId: UUID;
  chapterId: UUID;
  locked: boolean;
  onAcceptedSaved: (turn: AcceptedTurn) => void;
  paragraphs: AcceptedTurn[];
  sceneTitles?: Record<UUID, string>;
  justAcceptedIndex: number | null;
  pendingTurn: Turn | null;
  streaming: boolean;
  editing: boolean;
  busy: boolean;
  onEditSave: (content: string) => void;
  onEditCancel: () => void;
  onKeep: () => void;
  onRewrite: (instruction: string) => void;
  onEdit: () => void;
  onDiscard: () => void;
}) {
  const [selected, setSelected] = useState<{turnId: UUID; version: number; range: TextSelection | null} | null>(null);
  const empty = paragraphs.length === 0 && !pendingTurn;

  return (
    <div className={styles.sheet}>
      {empty && (
        <p className="font-manuscript text-[1.1875rem] italic text-muted-foreground">
          The page is blank. Tell it what happens first.
        </p>
      )}
      {paragraphs.map((turn, i) => (
        <div key={turn.id}>
          <Paragraph
            index={i}
            text={turn.content}
            justAccepted={i === justAcceptedIndex}
            onSelection={range => setSelected({turnId: turn.id, version: turn.version, range})}
          />
          {turn.scene_id && <p className="mt-1 text-xs text-muted-foreground">Scene: {sceneTitles[turn.scene_id] ?? "Linked scene"}</p>}
          <div className="flex flex-wrap items-baseline gap-3">
          <AcceptedParagraphEditor
            storyId={storyId}
            chapterId={chapterId}
            turn={turn}
            disabled={(!locked && busy) || editing}
            readOnly={locked}
            onSaved={onAcceptedSaved}
          />
          <RewriteDialog
            storyId={storyId}
            chapterId={chapterId}
            turn={turn}
            selection={selected?.turnId === turn.id && selected.version === turn.version ? selected.range : null}
            disabled={locked || busy || editing}
            onSaved={onAcceptedSaved}
          />
          </div>
        </div>
      ))}
      {pendingTurn && (
        <div>
          <PendingDraft
            index={paragraphs.length}
            content={pendingTurn.content}
            streaming={streaming}
            editing={editing}
            busy={busy}
            onEditSave={onEditSave}
            onEditCancel={onEditCancel}
          />
          {!editing && !streaming && (
            <DraftActions
              disabled={busy}
              onKeep={onKeep}
              onRewrite={onRewrite}
              onEdit={onEdit}
              onDiscard={onDiscard}
            />
          )}
        </div>
      )}
    </div>
  );
}
