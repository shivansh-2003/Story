import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import type { Character } from "@/lib/types";
import { createCharacter } from "./charactersApi";

// Asks for name + role only, then the caller opens CharacterSheet on the
// Identity tab so the other nine fields are progressive, not a wall of form.
export function NewCharacterDialog({ onCreated }: { onCreated: (character: Character) => void }) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [role, setRole] = useState("");
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => createCharacter({ name, role: role || null }),
    onSuccess: (character) => {
      queryClient.setQueryData<Character[]>(["characters"], (prev) => [...(prev ?? []), character]);
      setOpen(false);
      setName("");
      setRole("");
      onCreated(character);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>+ New character</Button>
      </DialogTrigger>
      <DialogContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>New character</DialogTitle>
          </DialogHeader>
          <div className="mt-4 flex flex-col gap-4">
            <div>
              <Label htmlFor="char-name" className="mb-1.5 block">Name</Label>
              <Input id="char-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus required />
            </div>
            <div>
              <Label htmlFor="char-role" className="mb-1.5 block">Role</Label>
              <Input
                id="char-role"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder="protagonist, rival, mentor…"
              />
            </div>
          </div>
          <DialogFooter className="mt-6">
            <Button type="submit" disabled={!name.trim() || mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create character"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
