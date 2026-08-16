import { AutosizeTextarea } from "@/components/AutosizeTextarea";
import { Button } from "@/components/ui/button";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";

type Length = "short" | "standard" | "long";

const LENGTH_HINT: Record<Length, string> = { short: "~50 words", standard: "~100 words", long: "~150 words" };

export function InstructionConsole({
  instruction,
  onInstructionChange,
  length,
  onLengthChange,
  generating,
  locked,
  onUnlock,
  onSubmit,
  onStop,
}: {
  instruction: string;
  onInstructionChange: (value: string) => void;
  length: Length;
  onLengthChange: (length: Length) => void;
  generating: boolean;
  locked: boolean;
  onUnlock: () => void;
  onSubmit: () => void;
  onStop: () => void;
}) {
  if (locked) {
    return (
      <div className="mt-6 rounded-lg border border-border bg-card p-4 text-sm text-muted-foreground">
        This chapter is locked.{" "}
        <button onClick={onUnlock} className="text-primary hover:underline">
          Unlock it
        </button>{" "}
        to keep writing.
      </div>
    );
  }

  return (
    <div className="mt-6 rounded-lg border border-border bg-card p-4">
      <AutosizeTextarea
        value={instruction}
        onChange={(e) => onInstructionChange(e.target.value)}
        onKeyDown={(e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
            e.preventDefault();
            onSubmit();
          }
        }}
        placeholder="What happens next?"
        rows={3}
        disabled={generating}
        className="border-none bg-transparent p-0 font-manuscript text-base shadow-none focus-visible:ring-0"
      />
      <div className="mt-3 flex items-center justify-between">
        <ToggleGroup type="single" value={length} onValueChange={(v) => v && onLengthChange(v as Length)}>
          {(["short", "standard", "long"] as const).map((l) => (
            <ToggleGroupItem key={l} value={l} className="font-mono text-xs uppercase tracking-wide" title={LENGTH_HINT[l]}>
              {l}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div className="flex items-center gap-2">
          <span className="hidden font-mono text-xs text-muted-foreground sm:inline">⌘⏎</span>
          {generating ? (
            <Button variant="outline" onClick={onStop}>
              Stop
            </Button>
          ) : (
            <Button onClick={onSubmit} disabled={!instruction.trim()}>
              Write the next part
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
