import { useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/EmptyState";
import { CharacterCard } from "@/features/characters/CharacterCard";
import { CharacterSheet } from "@/features/characters/CharacterSheet";
import { listCharacters } from "@/features/characters/charactersApi";
import type { StoryDetail } from "@/lib/types";
import { importCharacterToStory } from "./storiesApi";
import type { StoryOutletContext } from "./StoryLayout";

export function StoryCastTab() {
  const { story } = useOutletContext<StoryOutletContext>();
  const { storyId = "" } = useParams();
  const queryClient = useQueryClient();
  const { data: allCharacters } = useQuery({ queryKey: ["characters"], queryFn: () => listCharacters() });
  const [picked, setPicked] = useState("");
  const [openCharacterId, setOpenCharacterId] = useState<string | null>(null);

  const importedIds = new Set(story.characters.map((c) => c.id));
  const importable = allCharacters?.filter((c) => !importedIds.has(c.id)) ?? [];

  async function handleImport() {
    if (!picked) return;
    await importCharacterToStory(storyId, picked);
    queryClient.setQueryData(["story", storyId], (prev: StoryDetail) => ({
      ...prev,
      characters: [...prev.characters, allCharacters!.find((c) => c.id === picked)!],
    }));
    setPicked("");
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-4">
        <p className="text-sm text-muted-foreground">Characters active in this story.</p>
        {importable.length > 0 && (
          <div className="flex gap-2">
            <Select value={picked} onValueChange={setPicked}>
              <SelectTrigger className="w-56"><SelectValue placeholder="Import a character…" /></SelectTrigger>
              <SelectContent>
                {importable.map((c) => (
                  <SelectItem key={c.id} value={c.id}>{c.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Button variant="outline" disabled={!picked} onClick={handleImport}>
              Import
            </Button>
          </div>
        )}
      </div>

      {story.characters.length === 0 ? (
        <div className="mt-6">
          <EmptyState title="No cast imported yet." description="Bring in characters from your cast to write them into this story." />
        </div>
      ) : (
        <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {story.characters.map((c) => (
            <CharacterCard key={c.id} character={c} onClick={() => setOpenCharacterId(c.id)} />
          ))}
        </div>
      )}

      <CharacterSheet characterId={openCharacterId} onOpenChange={(open) => !open && setOpenCharacterId(null)} />
    </div>
  );
}
