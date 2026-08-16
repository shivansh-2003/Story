import { useState, type KeyboardEvent } from "react";
import { X } from "lucide-react";
import { cn } from "@/lib/utils";

// Chip input for genre / themes / traits — replaces comma-split strings so a
// comma inside a value (e.g. "coming-of-age, sort of") can't corrupt the list.
export function TokenInput({
  value,
  onChange,
  placeholder,
  className,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
  className?: string;
}) {
  const [draft, setDraft] = useState("");

  function commit() {
    const token = draft.trim();
    if (token && !value.includes(token)) onChange([...value, token]);
    setDraft("");
  }

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit();
    } else if (e.key === "Backspace" && draft === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div
      className={cn(
        "flex flex-wrap items-center gap-1.5 rounded-md border border-input bg-transparent px-3 py-2 text-sm focus-within:border-ring focus-within:ring-[3px] focus-within:ring-primary/60",
        className,
      )}
    >
      {value.map((token) => (
        <span
          key={token}
          className="inline-flex items-center gap-1 rounded-sm bg-secondary px-2 py-0.5 font-mono text-[0.6875rem] uppercase tracking-wide text-secondary-foreground"
        >
          {token}
          <button
            type="button"
            onClick={() => onChange(value.filter((t) => t !== token))}
            className="text-muted-foreground hover:text-destructive"
            aria-label={`Remove ${token}`}
          >
            <X className="size-3" />
          </button>
        </span>
      ))}
      <input
        className="min-w-24 flex-1 bg-transparent outline-none placeholder:text-muted-foreground"
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={handleKeyDown}
        onBlur={commit}
        placeholder={value.length === 0 ? placeholder : undefined}
      />
    </div>
  );
}
