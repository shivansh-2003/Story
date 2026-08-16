import { Lock } from "lucide-react";
import { cn } from "@/lib/utils";
import type { ChapterStatus, StoryStatus } from "@/lib/types";

const STORY_STATUS: Record<StoryStatus, { label: string; className: string }> = {
  draft: { label: "draft", className: "text-graphite" },
  ongoing: { label: "ongoing", className: "text-primary" },
  on_hold: { label: "on hold", className: "text-marigold" },
  completed: { label: "completed", className: "text-foreground" },
  abandoned: { label: "abandoned", className: "text-graphite/50" },
};

const CHAPTER_STATUS: Record<ChapterStatus, { label: string; className: string }> = {
  draft: { label: "draft", className: "text-graphite" },
  in_progress: { label: "in progress", className: "text-primary" },
  in_review: { label: "in review", className: "text-marigold" },
  complete: { label: "complete", className: "text-foreground" },
  locked: { label: "locked", className: "text-foreground" },
};

// Single mapping from story/chapter status → colour + label. Every screen
// that shows a status pill routes through here so the vocabulary never drifts.
export function StatusPill({
  status,
  kind,
  className,
}: {
  status: StoryStatus | ChapterStatus;
  kind: "story" | "chapter";
  className?: string;
}) {
  const map = kind === "story" ? STORY_STATUS : CHAPTER_STATUS;
  const entry = map[status as keyof typeof map];
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 font-mono text-[0.6875rem] font-medium tracking-[0.12em] uppercase",
        entry.className,
        className,
      )}
    >
      {entry.label}
      {status === "locked" && <Lock className="size-3" />}
    </span>
  );
}
