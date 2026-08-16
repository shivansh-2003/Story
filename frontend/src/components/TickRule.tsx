import { cn } from "@/lib/utils";

// Progress rendered as tick marks, not a bar — a story's chapter count and a
// chapter's word-count-vs-target both read the same way: filled vs. hollow.
export function TickRule({
  total,
  filled,
  className,
}: {
  total: number;
  filled: number;
  className?: string;
}) {
  if (total === 0) return null;
  return (
    <svg
      viewBox={`0 0 ${total * 6 - 2} 10`}
      width={total * 6 - 2}
      height={10}
      className={cn("shrink-0", className)}
      role="img"
      aria-label={`${filled} of ${total} complete`}
    >
      {Array.from({ length: total }, (_, i) => (
        <rect
          key={i}
          x={i * 6}
          y={0}
          width={2}
          height={10}
          rx={1}
          className={i < filled ? "fill-primary" : "fill-border"}
        />
      ))}
    </svg>
  );
}
