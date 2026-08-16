import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import type { StoryStatus } from "@/lib/types";
import { Input } from "@/components/ui/input";
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/EmptyState";
import { StoryCard } from "./StoryCard";
import { NewStoryDialog } from "./NewStoryDialog";
import { listStories } from "./storiesApi";

const FILTERS: { value: StoryStatus | "all"; label: string }[] = [
  { value: "all", label: "All" },
  { value: "ongoing", label: "Ongoing" },
  { value: "draft", label: "Draft" },
  { value: "on_hold", label: "On hold" },
  { value: "completed", label: "Done" },
];

export function StoryLibraryPage() {
  const { data: stories, isLoading } = useQuery({ queryKey: ["stories"], queryFn: listStories });
  const [filter, setFilter] = useState<StoryStatus | "all">("all");
  const [search, setSearch] = useState("");

  const filtered = useMemo(() => {
    if (!stories) return [];
    return stories.filter((s) => {
      if (filter !== "all" && s.status !== filter) return false;
      if (search && !s.title.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    });
  }, [stories, filter, search]);

  const ongoingCount = stories?.filter((s) => s.status === "ongoing").length ?? 0;

  return (
    <div>
      <div className="flex items-start justify-between">
        <div>
          <h1 className="font-display text-2xl font-medium">Your library</h1>
          {stories && (
            <p className="mt-1 text-sm text-muted-foreground">
              {stories.length} {stories.length === 1 ? "story" : "stories"} · {ongoingCount} ongoing
            </p>
          )}
        </div>
        <NewStoryDialog />
      </div>

      <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
        <ToggleGroup type="single" value={filter} onValueChange={(v) => v && setFilter(v as StoryStatus | "all")}>
          {FILTERS.map((f) => (
            <ToggleGroupItem key={f.value} value={f.value} className="font-mono text-xs uppercase tracking-wide">
              {f.label}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        <div className="relative">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search"
            className="h-8 w-48 pl-8 text-sm"
          />
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {isLoading &&
          Array.from({ length: 6 }, (_, i) => <Skeleton key={i} className="h-40 rounded-lg" />)}
        {!isLoading && filtered.map((story) => <StoryCard key={story.id} story={story} />)}
      </div>

      {!isLoading && stories?.length === 0 && (
        <div className="mt-6">
          <EmptyState
            title="Your library is empty."
            description="A story starts with a title. You can fill in the bible later."
            action={<NewStoryDialog />}
          />
        </div>
      )}
      {!isLoading && (stories?.length ?? 0) > 0 && filtered.length === 0 && (
        <p className="mt-10 text-center text-sm text-muted-foreground">No stories match that filter.</p>
      )}
    </div>
  );
}
