import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

export function DraftActions({
  disabled,
  onKeep,
  onRewrite,
  onEdit,
  onDiscard,
}: {
  disabled: boolean;
  onKeep: () => void;
  onRewrite: (instruction: string) => void;
  onEdit: () => void;
  onDiscard: () => void;
}) {
  const [rewriteOpen, setRewriteOpen] = useState(false);
  const [rewriteInstruction, setRewriteInstruction] = useState("");

  return (
    <div role="group" aria-label="What to do with this draft" className="mt-3 flex flex-wrap gap-2">
      <Button size="sm" onClick={onKeep} disabled={disabled}>
        Keep it
      </Button>

      <Popover open={rewriteOpen} onOpenChange={setRewriteOpen}>
        <PopoverTrigger asChild>
          <Button size="sm" variant="secondary" disabled={disabled}>
            Rewrite
          </Button>
        </PopoverTrigger>
        <PopoverContent align="start" className="flex w-72 gap-2">
          <Input
            value={rewriteInstruction}
            onChange={(e) => setRewriteInstruction(e.target.value)}
            placeholder="Rewrite it how?"
            autoFocus
            onKeyDown={(e) => {
              if (e.key === "Enter" && rewriteInstruction.trim()) {
                onRewrite(rewriteInstruction);
                setRewriteOpen(false);
                setRewriteInstruction("");
              }
            }}
          />
          <Button
            size="sm"
            disabled={!rewriteInstruction.trim()}
            onClick={() => {
              onRewrite(rewriteInstruction);
              setRewriteOpen(false);
              setRewriteInstruction("");
            }}
          >
            Go
          </Button>
        </PopoverContent>
      </Popover>

      <Button size="sm" variant="ghost" onClick={onEdit} disabled={disabled}>
        Edit
      </Button>
      <Button size="sm" variant="ghost" onClick={onDiscard} disabled={disabled} className="text-destructive hover:text-destructive">
        Throw away
      </Button>
    </div>
  );
}
