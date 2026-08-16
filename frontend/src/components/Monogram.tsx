import { cn } from "@/lib/utils";

// deterministic 5-step slate tint from the seed, not a random hue per user
const TINTS = ["bg-stock text-primary", "bg-secondary text-foreground", "bg-muted text-foreground"] as const;

function hashTint(seed: string): (typeof TINTS)[number] {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) hash = (hash * 31 + seed.charCodeAt(i)) | 0;
  return TINTS[Math.abs(hash) % TINTS.length];
}

function initials(label: string): string {
  const parts = label.trim().split(/[\s@.]+/).filter(Boolean);
  if (parts.length === 0) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[1][0]).toUpperCase();
}

const SIZES = { sm: "size-8 text-xs", md: "size-11 text-sm", lg: "size-14 text-base" } as const;

export function Monogram({
  seed,
  label,
  size = "md",
  className,
}: {
  seed: string;
  label: string;
  size?: keyof typeof SIZES;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center rounded-full font-display font-semibold",
        SIZES[size],
        hashTint(seed),
        className,
      )}
    >
      {initials(label)}
    </span>
  );
}
