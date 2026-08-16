import { Link, NavLink, Outlet, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft } from "lucide-react";
import { toast } from "sonner";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";
import { Select, SelectContent, SelectItem, SelectTrigger } from "@/components/ui/select";
import { StatusPill } from "@/components/StatusPill";
import type { StoryDetail, StoryStatus } from "@/lib/types";
import { getStory, updateStory } from "./storiesApi";

// Mirrors app/stories/models.py's STORY_TRANSITIONS — the backend 409s on
// any jump not listed here (e.g. draft -> completed), so the dropdown must
// only ever offer what will actually succeed. Keep in sync with the backend.
const STORY_TRANSITIONS: Record<StoryStatus, StoryStatus[]> = {
  draft: ["ongoing", "abandoned"],
  ongoing: ["on_hold", "completed", "abandoned"],
  on_hold: ["ongoing", "completed", "abandoned"],
  completed: ["ongoing"],
  abandoned: ["ongoing"],
};

const tabClass = ({ isActive }: { isActive: boolean }) =>
  cn(
    "border-b-2 px-1 py-3 text-sm font-medium transition-colors",
    isActive ? "border-primary text-foreground" : "border-transparent text-muted-foreground hover:text-foreground",
  );

export type StoryOutletContext = { story: StoryDetail };

export function StoryLayout() {
  const { storyId = "" } = useParams();
  const queryClient = useQueryClient();
  const { data: story } = useQuery({ queryKey: ["story", storyId], queryFn: () => getStory(storyId) });

  if (!story) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="h-10 w-96" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  const meta = [story.pov?.replace("_", " "), story.tense, story.setting].filter(Boolean).join(" · ");

  return (
    <div>
      <Link to="/library" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ChevronLeft className="size-4" /> Library
      </Link>

      <div className="mt-2 flex items-center justify-between gap-4">
        <h1 className="font-display text-2xl font-medium">{story.title}</h1>
        <Select
          value={story.status}
          onValueChange={(status: StoryStatus) =>
            updateStory(storyId, { status })
              .then((updated) =>
                queryClient.setQueryData(["story", storyId], (prev: StoryDetail) => ({ ...prev, ...updated })),
              )
              .catch((err: Error) => toast.error(err.message))
          }
        >
          <SelectTrigger size="sm" className="border-none shadow-none">
            <StatusPill status={story.status} kind="story" />
          </SelectTrigger>
          <SelectContent align="end" sideOffset={6}>
            {STORY_TRANSITIONS[story.status].map((s) => (
              <SelectItem key={s} value={s}>
                <StatusPill status={s} kind="story" />
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      {meta && <p className="mt-1 text-sm text-muted-foreground">{meta}</p>}

      <nav className="mt-4 flex gap-6 border-b border-border">
        <NavLink to="chapters" className={tabClass}>
          Chapters
        </NavLink>
        <NavLink to="cast" className={tabClass}>
          Cast · {story.characters.length}
        </NavLink>
        <NavLink to="bible" className={tabClass}>
          Bible
        </NavLink>
      </nav>

      <div className="mt-6">
        <Outlet context={{ story } satisfies StoryOutletContext} />
      </div>
    </div>
  );
}
