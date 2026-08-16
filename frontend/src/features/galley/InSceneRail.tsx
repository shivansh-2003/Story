import { useState, type FormEvent } from "react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

// There's no GET endpoint for a chapter's active-character list (only
// add/create-and-activate/remove) — so this rail can't show who's already
// in scene, only let you add someone. Same known gap the old writing room
// had; add a list here once the backend exposes one.
export function InSceneRail({
  onAdd,
  busy,
}: {
  onAdd: (name: string, role: string) => Promise<void>;
  busy: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    await onAdd(name, role);
    setName("");
    setRole("");
    setOpen(false);
  }

  return (
    <div>
      <h2 className="font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">In scene</h2>
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <button className="mt-2 text-sm text-muted-foreground underline decoration-dotted hover:text-primary">
            + someone new
          </button>
        </PopoverTrigger>
        <PopoverContent align="start" className="w-64">
          <form className="flex flex-col gap-2" onSubmit={handleSubmit}>
            <Input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" autoFocus required />
            <Input value={role} onChange={(e) => setRole(e.target.value)} placeholder="Role (optional)" />
            <Button size="sm" type="submit" disabled={busy || !name.trim()}>
              Add
            </Button>
          </form>
        </PopoverContent>
      </Popover>
    </div>
  );
}
