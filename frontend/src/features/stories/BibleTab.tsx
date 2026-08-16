import { useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AutosizeTextarea } from "@/components/AutosizeTextarea";
import { TokenInput } from "@/components/TokenInput";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { POV, StoryDetail, Tense } from "@/lib/types";
import { updateStory, type StoryInput } from "./storiesApi";
import type { StoryOutletContext } from "./StoryLayout";

function formFrom(story: StoryDetail): StoryInput {
  return {
    title: story.title,
    genre: story.genre ?? [],
    tone: story.tone ?? "",
    pov: story.pov,
    tense: story.tense,
    rating: story.rating ?? "",
    premise: story.premise ?? "",
    opening_line: story.opening_line ?? "",
    setting: story.setting ?? "",
    themes: story.themes ?? [],
    content_boundaries: story.content_boundaries ?? "",
    writing_style_notes: story.writing_style_notes ?? "",
    target_audience: story.target_audience ?? "",
  };
}

const ROWS: { key: keyof StoryInput; label: string }[] = [
  { key: "tone", label: "Tone" },
  { key: "pov", label: "POV" },
  { key: "tense", label: "Tense" },
  { key: "rating", label: "Rating" },
  { key: "target_audience", label: "Audience" },
  { key: "setting", label: "Setting" },
  { key: "premise", label: "Premise" },
  { key: "opening_line", label: "Opening line" },
  { key: "writing_style_notes", label: "Style notes" },
  { key: "content_boundaries", label: "Boundaries" },
];

export function BibleTab() {
  const { story } = useOutletContext<StoryOutletContext>();
  const { storyId = "" } = useParams();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [form, setForm] = useState<StoryInput>(() => formFrom(story));

  const save = useMutation({
    mutationFn: () =>
      updateStory(storyId, {
        ...form,
        genre: form.genre?.length ? form.genre : null,
        themes: form.themes?.length ? form.themes : null,
      }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["story", storyId], { ...story, ...updated });
      setEditing(false);
    },
  });

  if (!editing) {
    const values: Record<string, string> = {
      tone: story.tone ?? "—",
      pov: story.pov?.replace("_", " ") ?? "—",
      tense: story.tense ?? "—",
      rating: story.rating ?? "—",
      target_audience: story.target_audience ?? "—",
      setting: story.setting ?? "—",
      premise: story.premise ?? "—",
      opening_line: story.opening_line ?? "—",
      writing_style_notes: story.writing_style_notes ?? "—",
      content_boundaries: story.content_boundaries ?? "—",
    };
    return (
      <div>
        <div className="flex justify-end">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setForm(formFrom(story));
              setEditing(true);
            }}
          >
            Edit bible
          </Button>
        </div>
        {(story.genre?.length || story.themes?.length) && (
          <div className="mt-4 flex flex-wrap gap-1.5">
            {story.genre?.map((g) => (
              <span key={g} className="rounded-sm bg-secondary px-2 py-0.5 font-mono text-[0.6875rem] uppercase tracking-wide">
                {g}
              </span>
            ))}
            {story.themes?.map((t) => (
              <span key={t} className="rounded-sm border border-border px-2 py-0.5 font-mono text-[0.6875rem] uppercase tracking-wide text-muted-foreground">
                {t}
              </span>
            ))}
          </div>
        )}
        <dl className="mt-6 divide-y divide-border">
          {ROWS.map(({ key, label }) => (
            <div key={key} className="grid grid-cols-[8rem_1fr] gap-4 py-3">
              <dt className="font-mono text-xs uppercase tracking-wide text-muted-foreground">{label}</dt>
              <dd className="font-manuscript text-[1.0625rem] leading-relaxed">{values[key]}</dd>
            </div>
          ))}
        </dl>
      </div>
    );
  }

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(e) => {
        e.preventDefault();
        save.mutate();
      }}
    >
      <div>
        <Label className="mb-1.5 block">Title</Label>
        <Input value={form.title} onChange={(e) => setForm((f) => ({ ...f, title: e.target.value }))} required />
      </div>
      <div>
        <Label className="mb-1.5 block">Genre</Label>
        <TokenInput value={form.genre ?? []} onChange={(v) => setForm((f) => ({ ...f, genre: v }))} placeholder="literary, tense…" />
      </div>
      <div className="grid grid-cols-2 gap-4">
        <div>
          <Label className="mb-1.5 block">Tone</Label>
          <Input value={form.tone ?? ""} onChange={(e) => setForm((f) => ({ ...f, tone: e.target.value }))} />
        </div>
        <div>
          <Label className="mb-1.5 block">Rating</Label>
          <Input value={form.rating ?? ""} onChange={(e) => setForm((f) => ({ ...f, rating: e.target.value }))} />
        </div>
        <div>
          <Label className="mb-1.5 block">POV</Label>
          <Select value={form.pov ?? undefined} onValueChange={(v: POV) => setForm((f) => ({ ...f, pov: v }))}>
            <SelectTrigger className="w-full"><SelectValue placeholder="Unset" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="first_person">First person</SelectItem>
              <SelectItem value="third_limited">Third limited</SelectItem>
              <SelectItem value="third_omniscient">Third omniscient</SelectItem>
            </SelectContent>
          </Select>
        </div>
        <div>
          <Label className="mb-1.5 block">Tense</Label>
          <Select value={form.tense ?? undefined} onValueChange={(v: Tense) => setForm((f) => ({ ...f, tense: v }))}>
            <SelectTrigger className="w-full"><SelectValue placeholder="Unset" /></SelectTrigger>
            <SelectContent>
              <SelectItem value="past">Past</SelectItem>
              <SelectItem value="present">Present</SelectItem>
            </SelectContent>
          </Select>
        </div>
      </div>
      <div>
        <Label className="mb-1.5 block">Target audience</Label>
        <Input
          value={form.target_audience ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, target_audience: e.target.value }))}
        />
      </div>
      <div>
        <Label className="mb-1.5 block">Themes</Label>
        <TokenInput value={form.themes ?? []} onChange={(v) => setForm((f) => ({ ...f, themes: v }))} placeholder="duty, inheritance…" />
      </div>
      <div>
        <Label className="mb-1.5 block">Premise</Label>
        <AutosizeTextarea value={form.premise ?? ""} onChange={(e) => setForm((f) => ({ ...f, premise: e.target.value }))} />
      </div>
      <div>
        <Label className="mb-1.5 block">Setting</Label>
        <AutosizeTextarea value={form.setting ?? ""} onChange={(e) => setForm((f) => ({ ...f, setting: e.target.value }))} />
      </div>
      <div>
        <Label className="mb-1.5 block">Opening line</Label>
        <Input
          value={form.opening_line ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, opening_line: e.target.value }))}
        />
      </div>
      <div>
        <Label className="mb-1.5 block">Writing style notes</Label>
        <AutosizeTextarea
          value={form.writing_style_notes ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, writing_style_notes: e.target.value }))}
        />
      </div>
      <div>
        <Label className="mb-1.5 block">Content boundaries</Label>
        <AutosizeTextarea
          value={form.content_boundaries ?? ""}
          onChange={(e) => setForm((f) => ({ ...f, content_boundaries: e.target.value }))}
        />
      </div>
      <div className="flex gap-2">
        <Button type="submit" disabled={save.isPending}>
          {save.isPending ? "Saving…" : "Save"}
        </Button>
        <Button type="button" variant="ghost" onClick={() => setEditing(false)}>
          Cancel
        </Button>
      </div>
    </form>
  );
}
