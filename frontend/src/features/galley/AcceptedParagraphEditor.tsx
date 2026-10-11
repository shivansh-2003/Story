import { useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { AcceptedTurn, UUID } from "@/lib/types";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/apiFetch";
import { getChapter } from "@/features/chapters/chaptersApi";
import * as api from "./generationApi";

export function AcceptedParagraphEditor({
  storyId,
  chapterId,
  turn,
  disabled,
  readOnly,
  onSaved,
}: {
  storyId: UUID;
  chapterId: UUID;
  turn: AcceptedTurn;
  disabled: boolean;
  readOnly: boolean;
  onSaved: (turn: AcceptedTurn) => void;
}) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState(turn.content);
  const [base, setBase] = useState(turn);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const key = ["turn-revisions", storyId, chapterId, turn.id];
  const history = useQuery({
    queryKey: key,
    queryFn: () => api.getRevisions(storyId, chapterId, turn.id),
    enabled: open,
  });
  function changeOpen(value: boolean) {
    if (busy) return;
    if (value) {
      setDraft(turn.content);
      setBase(turn);
      setError(null);
      setConflict(false);
    }
    setOpen(value);
  }
  async function save(revisionId?: UUID) {
    setBusy(true);
    setError(null);
    try {
      const updated = revisionId
        ? await api.restoreRevision(storyId, chapterId, base, revisionId)
        : await api.editTurn(storyId, chapterId, base, draft);
      onSaved(updated);
      await Promise.all([
        client.invalidateQueries({ queryKey: ["chapter", storyId, chapterId] }),
        client.invalidateQueries({
          queryKey: ["chapter-memory", storyId, chapterId],
        }),
        client.invalidateQueries({ queryKey: key }),
      ]);
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
      setConflict(e instanceof ApiError && e.status === 409);
    } finally {
      setBusy(false);
    }
  }
  async function reload() {
    setBusy(true);
    try {
      const chapter = await getChapter(storyId, chapterId);
      const latest = chapter.turns.find((t) => t.id === turn.id);
      if (!latest) throw new Error("Paragraph no longer exists");
      setBase(latest);
      onSaved(latest);
      await client.invalidateQueries({ queryKey: key });
      setConflict(false);
      setError(
        "Latest version loaded. Your unsaved text is preserved; review it before saving.",
      );
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <Dialog open={open} onOpenChange={changeOpen}>
      <DialogTrigger asChild>
        <button
          disabled={disabled}
          className="mb-4 text-xs underline underline-offset-4 disabled:opacity-40"
          style={{ color: "rgb(var(--pending))" }}
          aria-label={`Edit paragraph ${turn.sequence + 1} or view its history`}
        >
          Edit · History{turn.version > 1 ? ` · v${turn.version}` : ""}
        </button>
      </DialogTrigger>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Paragraph {turn.sequence + 1}</DialogTitle>
          <DialogDescription>
            Edit accepted prose or restore an earlier version. Every change is
            saved in history.
          </DialogDescription>
        </DialogHeader>
        <label htmlFor={`edit-${turn.id}`} className="text-sm">
          Your text · version {base.version}
        </label>
        <Textarea
          id={`edit-${turn.id}`}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          disabled={busy || disabled || readOnly}
          className="min-h-48 font-manuscript"
          maxLength={50000}
        />
        {readOnly && (
          <p className="text-sm text-muted-foreground">
            Unlock this chapter to edit or restore text. History remains
            available.
          </p>
        )}
        <p className="text-xs text-muted-foreground">
          Saving reopens a completed chapter and refreshes AI memory. Pending
          drafts remain available for review.
        </p>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        {conflict && (
          <Button variant="outline" disabled={busy} onClick={reload}>
            Load latest version, preserve my text
          </Button>
        )}
        <div className="flex gap-2">
          <Button
            disabled={
              busy ||
              disabled ||
              readOnly ||
              conflict ||
              !draft.trim() ||
              draft === base.content
            }
            onClick={() => save()}
          >
            {busy ? "Saving…" : "Save paragraph"}
          </Button>
          <Button
            variant="outline"
            disabled={busy}
            onClick={() => changeOpen(false)}
          >
            Cancel
          </Button>
        </div>
        <h3 className="mt-2 font-medium">Revision history</h3>
        {history.isPending && <p className="text-sm">Loading history…</p>}
        {history.error && (
          <p role="alert" className="text-sm text-destructive">
            {history.error.message}
          </p>
        )}
        {history.data?.map((revision) => (
          <div key={revision.id} className="rounded-md border p-3">
            <div className="flex items-center justify-between gap-3">
              <span className="text-xs text-muted-foreground">
                v{revision.revision_number} ·{" "}
                {revision.source === "ai_rewrite" ? "AI rewrite · " : ""}
                {new Date(revision.created_at).toLocaleString()}
                {revision.restored_from
                  ? ` · restored from v${revision.restored_from}`
                  : ""}
              </span>
              <Button
                size="sm"
                variant="outline"
                disabled={
                  busy ||
                  disabled ||
                  readOnly ||
                  conflict ||
                  revision.content === base.content
                }
                onClick={() => save(revision.id)}
              >
                Restore
              </Button>
            </div>
            <p className="mt-2 whitespace-pre-wrap font-manuscript text-sm">
              {revision.content}
            </p>
          </div>
        ))}
      </DialogContent>
    </Dialog>
  );
}
