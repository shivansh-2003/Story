import { useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError } from "@/lib/apiFetch";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { cancelImport, commitImport, previewImport, type ImportCommit, type ImportPreview } from "./transfersApi";

type Mapping = { source_index: number; title: string; include: boolean };

const retryKey = (storyId: string) => `story_import_retry:${storyId}`;

function savedRequest(storyId: string): ImportCommit | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(retryKey(storyId)) ?? "null");
    if (value && typeof value.preview_token === "string" && typeof value.commit_key === "string"
      && typeof value.enrich_with_ai === "boolean" && Array.isArray(value.chapters)
      && value.chapters.length > 0 && value.chapters.length <= 100
      && value.chapters.every((c: {source_index?: unknown; title?: unknown}) =>
        typeof c.source_index === "number" && Number.isInteger(c.source_index) && c.source_index >= 0
        && typeof c.title === "string" && c.title.length <= 200)) return value;
  } catch { /* Browser storage may be unavailable. In-page retries still work. */ }
  return null;
}

export function ImportManuscriptDialog({ storyId }: { storyId: string }) {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<ImportPreview | null>(null);
  const [mapping, setMapping] = useState<Mapping[]>([]);
  const [enrich, setEnrich] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [commitKey, setCommitKey] = useState("");
  const [pendingRequest, setPendingRequest] = useState<ImportCommit | null>(() => savedRequest(storyId));
  const [attempted, setAttempted] = useState(Boolean(pendingRequest));

  function clearRequest() {
    setPendingRequest(null);
    try { sessionStorage.removeItem(retryKey(storyId)); } catch { /* Optional persistence. */ }
  }

  function reset() {
    clearRequest();
    setFile(null); setPreview(null); setMapping([]); setError(""); setEnrich(false); setAttempted(false);
  }

  function close(next: boolean) {
    if (busy) return;
    // An uncertain commit keeps its exact request so Retry cannot duplicate it.
    if (!next && attempted) { setOpen(false); return; }
    if (!next) {
      if (preview) void cancelImport(storyId, preview.preview_token).catch(() => {});
      reset();
    }
    setOpen(next);
  }

  async function upload() {
    if (!file) return;
    setBusy(true); setError("");
    try {
      const result = await previewImport(storyId, file);
      setPreview(result);
      setMapping(result.chapters.map(c => ({ source_index: c.index, title: c.title, include: true })));
      setCommitKey(crypto.randomUUID());
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  function move(index: number, direction: number) {
    setMapping(previous => {
      const next = previous.slice();
      [next[index], next[index + direction]] = [next[index + direction], next[index]];
      return next;
    });
  }

  async function save() {
    const request = pendingRequest ?? (preview ? {
      preview_token: preview.preview_token, commit_key: commitKey,
      chapters: mapping.filter(c => c.include).map(({ source_index, title }) => ({ source_index, title })),
      enrich_with_ai: enrich,
    } : null);
    if (!request) return;
    setPendingRequest(request);
    // Store only mapping/keys, never a second copy of manuscript prose.
    try { sessionStorage.setItem(retryKey(storyId), JSON.stringify(request)); } catch { /* In-page retry remains available. */ }
    setBusy(true); setError(""); setAttempted(true);
    try {
      const result = await commitImport(storyId, request);
      await queryClient.invalidateQueries({ queryKey: ["chapters", storyId] });
      toast.success(`Imported ${result.chapters.length} chapters and ${result.paragraph_count} paragraphs.`);
      reset(); setOpen(false);
    } catch (err) {
      setError((err as Error).message);
      if (err instanceof ApiError && err.status >= 400 && err.status < 500) {
        clearRequest();
        setAttempted(false);
        if (err.status === 410 || err.status === 404) { setPreview(null); setMapping([]); }
      }
    }
    finally { setBusy(false); }
  }

  const selected = mapping.filter(c => c.include);
  const selectedParagraphs = selected.reduce((count, c) => count + (preview?.chapters[c.source_index].paragraphs.length ?? 0), 0);

  return (
    <Dialog open={open} onOpenChange={close}>
      <DialogTrigger asChild><Button variant="outline" size="sm">{pendingRequest ? "Resolve pending import" : "Import manuscript"}</Button></DialogTrigger>
      <DialogContent className="sm:max-w-2xl max-h-[90vh] overflow-y-auto" showCloseButton={!busy && !attempted}>
        <DialogHeader>
          <DialogTitle>{preview ? "Review your import" : "Import manuscript"}</DialogTitle>
          <DialogDescription>Append new chapters to this story. Existing writing stays in place.</DialogDescription>
        </DialogHeader>
        {pendingRequest && !preview ? (
          <div className="space-y-3 text-sm">
            <p>An earlier import needs confirmation. Retry the saved request to retrieve its result or finish importing, without creating a duplicate batch.</p>
            <ul className="list-disc pl-5">{pendingRequest.chapters.map(c => <li key={c.source_index}>{c.title}</li>)}</ul>
          </div>
        ) : !preview ? (
          <div className="space-y-3">
            <Label htmlFor="manuscript-file">UTF-8 text or Markdown file</Label>
            <Input id="manuscript-file" type="file" accept=".txt,.md" disabled={busy} onChange={e => setFile(e.target.files?.[0] ?? null)} />
            <p className="text-sm text-muted-foreground">Blank lines separate paragraphs. Text uses “Chapter 1: Title”; Markdown uses “## Title” for chapters. Preview lets you check the result before saving.</p>
          </div>
        ) : (
          <div className="space-y-4">
            <p className="text-sm text-muted-foreground">Rename, exclude, or reorder chapters below. Preview expires at {new Date(preview.expires_at).toLocaleTimeString()}.</p>
            {mapping.map((chapter, index) => (
              <div key={chapter.source_index} className="rounded-md border p-3 space-y-2">
                <div className="flex items-center gap-2">
                  <input type="checkbox" aria-label={`Include source chapter ${chapter.source_index + 1}`} checked={chapter.include} disabled={busy || attempted}
                    onChange={e => setMapping(prev => prev.map(c => c.source_index === chapter.source_index ? { ...c, include: e.target.checked } : c))} />
                  <Input aria-label={`Title for source chapter ${chapter.source_index + 1}`} value={chapter.title} maxLength={200} disabled={busy || attempted}
                    onChange={e => setMapping(prev => prev.map(c => c.source_index === chapter.source_index ? { ...c, title: e.target.value } : c))} />
                  <Button variant="ghost" size="sm" aria-label={`Move source chapter ${chapter.source_index + 1} up`} disabled={index === 0 || busy || attempted} onClick={() => move(index, -1)}>↑</Button>
                  <Button variant="ghost" size="sm" aria-label={`Move source chapter ${chapter.source_index + 1} down`} disabled={index === mapping.length - 1 || busy || attempted} onClick={() => move(index, 1)}>↓</Button>
                </div>
                <details className="text-sm">
                  <summary className="cursor-pointer text-muted-foreground">{preview.chapters[chapter.source_index].paragraphs.length} paragraphs · View text</summary>
                  <div className="mt-2 max-h-48 overflow-y-auto space-y-3">
                    {preview.chapters[chapter.source_index].paragraphs.map((text, i) => <p key={i} className="whitespace-pre-wrap">{text}</p>)}
                  </div>
                </details>
              </div>
            ))}
            <label className="flex items-start gap-2 text-sm">
              <input type="checkbox" checked={enrich} disabled={busy || attempted} onChange={e => setEnrich(e.target.checked)} className="mt-1" />
              <span>Refresh AI memory after import<span className="block text-muted-foreground">Optional. Summaries use your configured model; embeddings require OpenAI credentials. Writing is saved even if refresh fails.</span></span>
            </label>
            <p className="text-sm">Selected: {selected.length} chapters · {selectedParagraphs} paragraphs</p>
          </div>
        )}
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        {attempted && !busy && <p className="text-sm text-muted-foreground">Retry uses the same import request, so a lost response will not create duplicate chapters.</p>}
        <DialogFooter>
          <Button variant="outline" disabled={busy} onClick={() => close(false)}>{attempted ? "Close; retry later" : "Cancel"}</Button>
          {preview || pendingRequest ? <Button disabled={busy || (!pendingRequest && (!selectedParagraphs || selected.some(c => !c.title.trim())))} onClick={save}>{busy ? "Importing…" : attempted ? "Retry import" : "Import selected chapters"}</Button>
            : <Button disabled={busy || !file} onClick={upload}>{busy ? "Reading…" : "Preview import"}</Button>}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
