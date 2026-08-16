import type { Character } from "@/lib/types";
import { Monogram } from "@/components/Monogram";

export function CharacterCard({ character, onClick }: { character: Character; onClick: () => void }) {
  const traits = character.personality_traits ?? [];
  return (
    <button
      onClick={onClick}
      className="flex flex-col items-start gap-3 rounded-lg border border-border bg-card p-4 text-left shadow-[var(--shadow-raised)] transition-colors hover:border-primary/40"
    >
      <div className="flex w-full items-center gap-3">
        <Monogram seed={character.id} label={character.name} />
        <div className="min-w-0">
          <div className="flex items-baseline gap-1.5">
            <span className="truncate font-display text-base font-medium">{character.name}</span>
            {character.pronouns && (
              <span className="shrink-0 font-mono text-[0.6875rem] text-muted-foreground">{character.pronouns}</span>
            )}
          </div>
          <span className="text-xs text-muted-foreground">{character.role ?? "no role set"}</span>
        </div>
      </div>
      {traits.length > 0 ? (
        <div className="flex flex-wrap gap-1">
          {traits.slice(0, 3).map((t) => (
            <span key={t} className="rounded-sm bg-secondary px-1.5 py-0.5 text-[0.6875rem] text-secondary-foreground">
              {t}
            </span>
          ))}
          {traits.length > 3 && <span className="text-[0.6875rem] text-muted-foreground">+{traits.length - 3}</span>}
        </div>
      ) : (
        <span className="text-[0.6875rem] text-muted-foreground">no traits yet</span>
      )}
    </button>
  );
}
