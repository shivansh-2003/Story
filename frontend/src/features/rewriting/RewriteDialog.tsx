import { useRef, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/apiFetch";
import type { AcceptedTurn, UUID } from "@/lib/types";
import { getChapter } from "@/features/chapters/chaptersApi";
import * as api from "./rewritingApi";
import { fromUtf16, wholeParagraph } from "./selection";

export function RewriteDialog({ storyId, chapterId, turn, selection, disabled, onSaved }: {
  storyId: UUID; chapterId: UUID; turn: AcceptedTurn; selection?: api.TextSelection | null;
  disabled: boolean; onSaved: (turn: AcceptedTurn) => void;
}) {
  const client = useQueryClient();
  const [open, setOpen] = useState(false);
  const [base, setBase] = useState(turn);
  const [range, setRange] = useState(wholeParagraph(turn.content));
  const [instruction, setInstruction] = useState("");
  const [local, setLocal] = useState<api.RewriteProposal | null>(null);
  const [ignoreRecovered, setIgnoreRecovered] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflict, setConflict] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);
  const textRef = useRef<HTMLTextAreaElement>(null);
  const storageKey = `rewrite-proposal:${storyId}:${chapterId}:${turn.id}`;
  const key = ["rewrite-proposals", storyId, chapterId, turn.id];
  function remember(id: string | null) {
    try { if (id) sessionStorage.setItem(storageKey, id); else sessionStorage.removeItem(storageKey); } catch { /* Server list still supports recovery. */ }
  }
  const recovered = useQuery({
    queryKey: key,
    enabled: open && !ignoreRecovered,
    queryFn: async () => {
      let id: string | null = null;
      try { id = sessionStorage.getItem(storageKey); } catch { /* Fall back to saved proposals. */ }
      if (id) {
        try { return await api.getRewrite(storyId, chapterId, turn.id, id); }
        catch (e) { if (!(e instanceof ApiError) || e.status !== 404) throw e; remember(null); }
      }
      return (await api.listRewrites(storyId, chapterId, turn.id))[0] ?? null;
    },
    refetchInterval: query => query.state.data?.status === "generating" && Date.parse(query.state.data.expires_at) > Date.now() ? 2500 : false,
    staleTime: 0,
  });
  const proposal = local ?? (!ignoreRecovered ? recovered.data : null);
  const active = proposal && ["generating", "ready"].includes(proposal.status);
  const expired = !!proposal && Date.parse(proposal.expires_at) <= Date.now();
  function changeOpen(value: boolean) {
    if (busy) return;
    if (value) {
      setBase(turn); setRange(selection ?? wholeParagraph(turn.content));
      setLocal(null); setIgnoreRecovered(false); setError(null); setConflict(false); setNotice(null);
    }
    setOpen(value);
  }
  async function refreshManuscript() {
    const chapter = await getChapter(storyId, chapterId);
    const latest = chapter.turns.find(t => t.id === turn.id);
    if (!latest) throw new Error("Paragraph no longer exists.");
    onSaved(latest);
    client.setQueryData(["chapter", storyId, chapterId], chapter);
    await Promise.all([
      client.invalidateQueries({ queryKey: ["chapter-memory", storyId, chapterId] }),
      client.invalidateQueries({ queryKey: ["turn-revisions", storyId, chapterId, turn.id] }),
    ]);
    return latest;
  }
  async function generate() {
    setBusy(true); setError(null); setConflict(false); setNotice(null);
    const id = crypto.randomUUID();
    remember(id); setLocal(null); setIgnoreRecovered(true);
    try {
      const result = await api.generateRewrite(storyId, chapterId, turn.id, {
        ...range, proposal_id: id, expected_version: base.version, instruction,
      });
      setLocal(result); client.setQueryData(key, result);
    } catch (e) {
      setError((e as Error).message);
      setConflict(e instanceof ApiError && e.status === 409);
      // Response loss can leave a completed server proposal: recover by its ID.
      setIgnoreRecovered(false); await client.invalidateQueries({ queryKey: key });
    } finally { setBusy(false); }
  }
  async function apply() {
    if (!proposal) return;
    setBusy(true); setError(null);
    try {
      const receipt = await api.applyRewrite(storyId, chapterId, turn.id, proposal.id);
      await refreshManuscript();
      remember(null); setLocal(null); setIgnoreRecovered(true);
      setNotice(`Rewrite ${receipt.already_applied ? "was already" : "is"} applied as version ${receipt.applied_version}.`);
      setOpen(false);
    } catch (e) {
      setError((e as Error).message);
      setConflict(e instanceof ApiError && e.status === 409);
    } finally { setBusy(false); }
  }
  async function cancel() {
    setBusy(true); setError(null);
    try {
      if (proposal && proposal.status !== "applied") await api.cancelRewrite(storyId, chapterId, turn.id, proposal.id);
      remember(null); setLocal(null); setIgnoreRecovered(true); setConflict(false); setOpen(false);
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  async function startAgain() {
    setBusy(true); setError(null);
    try {
      if (proposal && proposal.status !== "applied") await api.cancelRewrite(storyId, chapterId, turn.id, proposal.id);
      const latest = await refreshManuscript();
      setBase(latest); setRange(wholeParagraph(latest.content));
      if (proposal) setInstruction(proposal.instruction);
      remember(null); setLocal(null); setIgnoreRecovered(true); setConflict(false);
      setNotice("Latest paragraph loaded. Select the text again, then generate a new suggestion.");
    } catch (e) { setError((e as Error).message); }
    finally { setBusy(false); }
  }
  function useSelection() {
    const input = textRef.current;
    if (!input) return;
    const selected = fromUtf16(base.content, input.selectionStart, input.selectionEnd);
    if (selected) { setRange(selected); setNotice("Selected text will be rewritten."); }
    else setNotice("Highlight text in the paragraph first.");
  }
  return <Dialog open={open} onOpenChange={changeOpen}>
    <DialogTrigger asChild><button disabled={disabled} className="mb-4 text-xs underline underline-offset-4 disabled:opacity-40" style={{color: "rgb(var(--pending))"}} aria-label={`AI rewrite paragraph ${turn.sequence + 1}`}>AI rewrite</button></DialogTrigger>
    <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-3xl" onKeyDown={e => e.stopPropagation()}>
      <DialogHeader><DialogTitle>Rewrite paragraph {turn.sequence + 1}</DialogTitle><DialogDescription>Review an AI suggestion before applying it. Only the chosen text changes; each applied change is saved in history.</DialogDescription></DialogHeader>
      {(!proposal || !active && proposal.status !== "applied") && <>
        <label className="space-y-1 text-sm">Paragraph · version {base.version}<Textarea ref={textRef} readOnly value={base.content} className="min-h-32 font-manuscript" /></label>
        <div className="flex flex-wrap gap-2"><Button size="sm" variant="outline" disabled={busy} onClick={useSelection}>Use selected text</Button><Button size="sm" variant="outline" disabled={busy} onClick={() => setRange(wholeParagraph(base.content))}>Use whole paragraph</Button></div>
        <p className="text-xs text-muted-foreground">Choose up to 12,000 characters from one paragraph.</p>
        <div className="rounded-md border p-3"><p className="mb-2 text-sm font-medium">Text to rewrite</p><p className="whitespace-pre-wrap font-manuscript text-sm">{range.original_text}</p></div>
        <label className="space-y-1 text-sm">Rewrite instruction<Textarea value={instruction} onChange={e => setInstruction(e.target.value)} maxLength={2000} disabled={busy} placeholder="Make this more suspenseful, while keeping the same events." /></label>
        <Button disabled={disabled || busy || recovered.isFetching || !instruction.trim() || !range.original_text.trim() || Array.from(range.original_text).length > 12000 || conflict} onClick={generate}>{busy ? "Generating suggestion…" : "Generate suggestion"}</Button>
      </>}
      {proposal && <>
        <p className="text-xs text-muted-foreground">Saved suggestion · source v{proposal.base_turn_version} · expires {new Date(proposal.expires_at).toLocaleTimeString()}</p>
        <p className="text-sm">Instruction: {proposal.instruction}</p>
        {proposal.status === "generating" && <p role="status">Suggestion is generating. Use “Check saved suggestion” to recover it if the response was interrupted.</p>}
        {proposal.status === "ready" && <div className="grid gap-4 sm:grid-cols-2"><div className="rounded-md border p-3"><p className="mb-2 text-sm font-medium">Original selection</p><p className="whitespace-pre-wrap font-manuscript text-sm">{proposal.original_text}</p></div><div className="rounded-md border p-3"><p className="mb-2 text-sm font-medium">AI suggestion</p><p className="whitespace-pre-wrap font-manuscript text-sm">{proposal.proposed_text}</p></div></div>}
        {proposal.status === "applied" && <p role="status">This rewrite was already applied as version {proposal.applied_version}. The manuscript remains at its latest version.</p>}
        {proposal.status === "failed" && <p role="alert">Suggestion generation failed. Your manuscript is unchanged.</p>}
        {proposal.status === "cancelled" && <p>This suggestion was cancelled.</p>}
        {expired && proposal.status !== "applied" && <p role="alert">This suggestion expired. Load the latest paragraph and generate a new one.</p>}
        {proposal.status === "ready" && <Button disabled={disabled || busy || conflict || expired} onClick={apply}>{busy ? "Applying…" : "Apply suggestion"}</Button>}
      </>}
      {(conflict || proposal) && <Button variant="outline" disabled={busy} onClick={startAgain}>Load latest paragraph and start again</Button>}
      {recovered.isError && <p role="alert" className="text-sm text-destructive">Could not load saved suggestions: {recovered.error.message}</p>}
      {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
      {notice && <p role="status" className="text-sm">{notice}</p>}
      <div className="flex flex-wrap gap-2"><Button variant="outline" disabled={busy} onClick={() => { setLocal(null); setIgnoreRecovered(false); void recovered.refetch(); }}>Check saved suggestion</Button><Button variant="outline" disabled={busy} onClick={cancel}>{active ? "Cancel suggestion" : "Close"}</Button></div>
      <p className="text-xs text-muted-foreground">Closing this window keeps a saved suggestion available for 30 minutes. Cancelling does not change the manuscript.</p>
    </DialogContent>
  </Dialog>;
}
