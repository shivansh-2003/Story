import type { Turn } from "@/lib/types";

// Clicking a sibling swaps it in as the current draft directly. The spec's
// hover-to-ghost-preview-above-the-draft interaction is a nice-to-have on
// top of this, not required for the attempts to be usable — cut for now.
export function AttemptsRail({ attempts, onRestore }: { attempts: Turn[]; onRestore: (turn: Turn) => void }) {
  if (attempts.length === 0) return null;

  return (
    <div className="flex flex-col gap-2">
      <h2 className="font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">Attempts</h2>
      {attempts.map((turn, i) => (
        <button
          key={i}
          onClick={() => onRestore(turn)}
          className="rounded-md border border-dashed border-graphite/60 px-2 py-1.5 text-left font-mono text-xs text-muted-foreground opacity-45 transition-opacity hover:opacity-100 hover:border-primary hover:text-foreground"
        >
          ◇ {i + 1}
        </button>
      ))}
    </div>
  );
}
