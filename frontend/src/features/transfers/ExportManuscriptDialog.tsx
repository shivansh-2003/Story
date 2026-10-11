import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { downloadManuscript } from "./transfersApi";

export function ExportManuscriptDialog({ storyId, title }: { storyId: string; title: string }) {
  const [open, setOpen] = useState(false);
  const [format, setFormat] = useState<"txt" | "md">("txt");
  const [archived, setArchived] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function download() {
    setBusy(true); setError("");
    try { await downloadManuscript(storyId, title, format, archived); setOpen(false); }
    catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  return (
    <Dialog open={open} onOpenChange={next => { if (!busy) { setOpen(next); setError(""); } }}>
      <DialogTrigger asChild><Button variant="outline" size="sm">Export manuscript</Button></DialogTrigger>
      <DialogContent showCloseButton={!busy}>
        <DialogHeader><DialogTitle>Export manuscript</DialogTitle><DialogDescription>Download accepted writing in chapter order. Pending drafts are excluded.</DialogDescription></DialogHeader>
        <label className="flex flex-col gap-2 text-sm">Format
          <select className="rounded-md border bg-background p-2" value={format} disabled={busy} onChange={e => setFormat(e.target.value as "txt" | "md")}>
            <option value="txt">Plain text (.txt)</option><option value="md">Markdown (.md)</option>
          </select>
        </label>
        <label className="flex gap-2 text-sm"><input type="checkbox" checked={archived} disabled={busy} onChange={e => setArchived(e.target.checked)} />Include archived chapters</label>
        {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
        <DialogFooter><Button disabled={busy} onClick={download}>{busy ? "Preparing…" : "Download manuscript"}</Button></DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
