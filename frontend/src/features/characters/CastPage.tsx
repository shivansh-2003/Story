import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { CharacterCard } from "./CharacterCard";
import { CharacterSheet } from "./CharacterSheet";
import { NewCharacterDialog } from "./NewCharacterDialog";
import { listCharacters } from "./charactersApi";

export function CastPage() {
  const { data: characters, isLoading } = useQuery({ queryKey: ["characters"], queryFn: () => listCharacters() });
  const [openCharacterId, setOpenCharacterId] = useState<string | null>(null);

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium">The cast</h1>
          {characters && (
            <p className="mt-1 text-sm text-muted-foreground">
              {characters.length} {characters.length === 1 ? "character" : "characters"}
            </p>
          )}
        </div>
        <NewCharacterDialog onCreated={(c) => setOpenCharacterId(c.id)} />
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        {isLoading && Array.from({ length: 8 }, (_, i) => <Skeleton key={i} className="h-32 rounded-lg" />)}
        {!isLoading &&
          characters?.map((c) => (
            <CharacterCard key={c.id} character={c} onClick={() => setOpenCharacterId(c.id)} />
          ))}
      </div>

      {!isLoading && characters?.length === 0 && (
        <div className="mt-6">
          <EmptyState
            title="Your cast is empty."
            description="Characters you create here can be imported into any story."
            action={<NewCharacterDialog onCreated={(c) => setOpenCharacterId(c.id)} />}
          />
        </div>
      )}

      <CharacterSheet characterId={openCharacterId} onOpenChange={(open) => !open && setOpenCharacterId(null)} />
    </div>
  );
}
