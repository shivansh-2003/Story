import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AutosizeTextarea } from "@/components/AutosizeTextarea";
import { TokenInput } from "@/components/TokenInput";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import type { Character } from "@/lib/types";
import {
  addRelationship,
  getCharacter,
  listCharacters,
  listRelationships,
  updateCharacter,
  type CharacterInput,
} from "./charactersApi";

function formFrom(c: Character) {
  return {
    name: c.name,
    role: c.role ?? "",
    age: c.age ?? "",
    pronouns: c.pronouns ?? "",
    appearance: c.appearance ?? "",
    voice_notes: c.voice_notes ?? "",
    personality_traits: c.personality_traits ?? [],
    motivation: c.motivation ?? "",
    flaw: c.flaw ?? "",
    backstory: c.backstory ?? "",
    condensed_summary: c.condensed_summary ?? "",
  };
}
type FormState = ReturnType<typeof formFrom>;

export function CharacterSheet({
  characterId,
  onOpenChange,
  initialTab = "identity",
}: {
  characterId: string | null;
  onOpenChange: (open: boolean) => void;
  initialTab?: string;
}) {
  const queryClient = useQueryClient();
  const { data: character } = useQuery({
    queryKey: ["character", characterId],
    queryFn: () => getCharacter(characterId!),
    enabled: !!characterId,
    // The card grid's ["characters"] list already has the full record (the
    // list endpoint doesn't return an abridged shape) — seed from it so
    // opening the drawer doesn't re-fetch data already in cache.
    initialData: () => queryClient.getQueryData<Character[]>(["characters"])?.find((c) => c.id === characterId),
  });
  const [form, setForm] = useState<FormState | null>(null);
  const [savedFlash, setSavedFlash] = useState(false);

  useEffect(() => {
    if (character) setForm(formFrom(character));
  }, [character]);

  const save = useMutation({
    mutationFn: (body: Partial<CharacterInput & { condensed_summary: string }>) =>
      updateCharacter(characterId!, body),
    onSuccess: (updated) => {
      queryClient.setQueryData(["character", characterId], updated);
      queryClient.setQueryData<Character[]>(["characters"], (prev) =>
        prev?.map((c) => (c.id === updated.id ? updated : c)),
      );
      setSavedFlash(true);
      setTimeout(() => setSavedFlash(false), 1400);
    },
  });

  function field<K extends keyof FormState>(key: K) {
    return {
      value: form?.[key] ?? "",
      onChange: (e: { target: { value: FormState[K] } }) => setForm((f) => (f ? { ...f, [key]: e.target.value } : f)),
      onBlur: () => {
        if (!form || !character) return;
        if (form[key] === (character[key as keyof Character] ?? (Array.isArray(form[key]) ? [] : ""))) return;
        save.mutate({ [key]: form[key] || null } as Partial<CharacterInput>);
      },
    };
  }

  return (
    <Sheet open={!!characterId} onOpenChange={onOpenChange}>
      <SheetContent className="w-full gap-0 overflow-y-auto sm:max-w-[520px]">
        <SheetHeader className="flex-row items-center justify-between space-y-0 border-b border-border">
          <SheetTitle className="font-display text-lg">{form?.name || "Character"}</SheetTitle>
          {savedFlash && <span className="font-mono text-[0.6875rem] uppercase tracking-wide text-primary">Saved</span>}
        </SheetHeader>

        {!form || !character ? (
          <div className="p-6 text-sm text-muted-foreground">Loading…</div>
        ) : (
          <Tabs defaultValue={initialTab} className="flex-1 gap-0">
            <TabsList className="w-full justify-start rounded-none border-b border-border bg-transparent px-4">
              <TabsTrigger value="identity">Identity</TabsTrigger>
              <TabsTrigger value="page">On the page</TabsTrigger>
              <TabsTrigger value="surface">Under the surface</TabsTrigger>
              <TabsTrigger value="summary">Prompt summary</TabsTrigger>
              <TabsTrigger value="relationships">Relationships</TabsTrigger>
            </TabsList>

            <TabsContent value="identity" className="flex flex-col gap-4 p-4">
              <FieldRow label="Name">
                <Input {...field("name")} />
              </FieldRow>
              <FieldRow label="Role">
                <Input {...field("role")} placeholder="protagonist, rival, mentor…" />
              </FieldRow>
              <FieldRow label="Age">
                <Input {...field("age")} />
              </FieldRow>
              <FieldRow label="Pronouns">
                <Input {...field("pronouns")} />
              </FieldRow>
            </TabsContent>

            <TabsContent value="page" className="flex flex-col gap-4 p-4">
              <FieldRow label="Appearance">
                <AutosizeTextarea {...field("appearance")} />
              </FieldRow>
              <FieldRow label="Voice notes" hint="how they talk">
                <AutosizeTextarea {...field("voice_notes")} />
              </FieldRow>
              <FieldRow label="Personality traits">
                <TokenInput
                  value={form.personality_traits}
                  onChange={(next) => {
                    setForm((f) => (f ? { ...f, personality_traits: next } : f));
                    save.mutate({ personality_traits: next.length ? next : null });
                  }}
                  placeholder="stubborn, dry humour…"
                />
              </FieldRow>
            </TabsContent>

            <TabsContent value="surface" className="flex flex-col gap-4 p-4">
              <FieldRow label="Motivation">
                <AutosizeTextarea {...field("motivation")} />
              </FieldRow>
              <FieldRow label="Flaw">
                <AutosizeTextarea {...field("flaw")} />
              </FieldRow>
              <FieldRow label="Backstory">
                <AutosizeTextarea {...field("backstory")} />
              </FieldRow>
            </TabsContent>

            <TabsContent value="summary" className="flex flex-col gap-2 p-4">
              <FieldRow label="Condensed summary">
                <AutosizeTextarea {...field("condensed_summary")} />
              </FieldRow>
              <div className="flex items-center justify-between">
                <p className="text-xs text-muted-foreground">
                  This is the line the model actually sees. Keep it under 200 characters.
                </p>
                <span
                  className={cn(
                    "shrink-0 font-mono text-xs",
                    form.condensed_summary.length > 200 ? "text-destructive" : "text-muted-foreground",
                  )}
                >
                  {form.condensed_summary.length}/200
                </span>
              </div>
            </TabsContent>

            <TabsContent value="relationships" className="p-4">
              <RelationshipsTab characterId={character.id} />
            </TabsContent>
          </Tabs>
        )}
      </SheetContent>
    </Sheet>
  );
}

function FieldRow({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <div>
      <Label className="mb-1.5 block">
        {label}
        {hint && <span className="ml-1.5 font-normal text-muted-foreground">({hint})</span>}
      </Label>
      {children}
    </div>
  );
}

function RelationshipsTab({ characterId }: { characterId: string }) {
  const queryClient = useQueryClient();
  const { data: relationships } = useQuery({
    queryKey: ["relationships", characterId],
    queryFn: () => listRelationships(characterId),
  });
  const { data: characters } = useQuery({ queryKey: ["characters"], queryFn: () => listCharacters() });
  const [target, setTarget] = useState("");
  const [label, setLabel] = useState("");

  const add = useMutation({
    mutationFn: () => addRelationship(characterId, target, label || undefined),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["relationships", characterId] });
      setTarget("");
      setLabel("");
    },
  });

  const others = characters?.filter((c) => c.id !== characterId) ?? [];
  const byId = new Map(others.map((c) => [c.id, c.name]));

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-col gap-1.5">
        {relationships?.length === 0 && <p className="text-sm text-muted-foreground">No relationships yet.</p>}
        {relationships?.map((r) => (
          <div key={r.id} className="flex items-center gap-2 rounded-md border border-border px-3 py-2 text-sm">
            <span className="font-mono text-xs text-muted-foreground">→</span>
            <span className="font-medium">{byId.get(r.related_character_id) ?? "unknown"}</span>
            {r.relationship_label && <span className="text-muted-foreground">: {r.relationship_label}</span>}
          </div>
        ))}
      </div>
      <div className="flex gap-2">
        <Select value={target} onValueChange={setTarget}>
          <SelectTrigger className="flex-1">
            <SelectValue placeholder="Character" />
          </SelectTrigger>
          <SelectContent>
            {others.map((c) => (
              <SelectItem key={c.id} value={c.id}>
                {c.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="label" className="flex-1" />
        <Button size="sm" disabled={!target || add.isPending} onClick={() => add.mutate()}>
          Add
        </Button>
      </div>
    </div>
  );
}
