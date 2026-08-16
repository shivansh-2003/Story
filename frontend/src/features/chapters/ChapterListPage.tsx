import { useEffect, useRef, useState } from "react";
import { useOutletContext, useParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Reorder } from "motion/react";
import { toast } from "sonner";
import { Monogram } from "@/components/Monogram";
import { EmptyState } from "@/components/EmptyState";
import { Skeleton } from "@/components/ui/skeleton";
import type { Chapter } from "@/lib/types";
import type { StoryOutletContext } from "@/features/stories/StoryLayout";
import { ChapterRow } from "./ChapterRow";
import { AddChapterRow } from "./AddChapterRow";
import { archiveChapter, createChapter, listChapters, lockChapter, reorderChapters, unlockChapter, updateChapter } from "./chaptersApi";

export function ChapterListPage() {
  const { story } = useOutletContext<StoryOutletContext>();
  const { storyId = "" } = useParams();
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["chapters", storyId], queryFn: () => listChapters(storyId) });
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const reorderTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => {
    if (data) setChapters(data.slice().sort((a, b) => a.order_index - b.order_index));
  }, [data]);

  function invalidate() {
    queryClient.invalidateQueries({ queryKey: ["chapters", storyId] });
  }

  function handleReorder(next: Chapter[]) {
    const previous = chapters;
    setChapters(next);
    if (reorderTimer.current) clearTimeout(reorderTimer.current);
    reorderTimer.current = setTimeout(() => {
      reorderChapters(
        storyId,
        next.map((c, i) => ({ chapter_id: c.id, order_index: i })),
      ).catch(() => {
        setChapters(previous);
        toast.error("Couldn't save the new order. Put back as it was.");
      });
    }, 400);
  }

  async function handleAdd(title: string) {
    const chapter = await createChapter(storyId, { title: title || null });
    setChapters((c) => [...c, chapter]);
  }

  async function handleRename(chapter: Chapter, title: string) {
    await updateChapter(storyId, chapter.id, { title: title || null });
    invalidate();
  }

  async function handleSetTargetLength(chapter: Chapter, words: number | null) {
    await updateChapter(storyId, chapter.id, { target_length_words: words });
    invalidate();
  }

  async function handleToggleLock(chapter: Chapter) {
    if (chapter.status === "locked") await unlockChapter(storyId, chapter.id);
    else await lockChapter(storyId, chapter.id);
    invalidate();
  }

  async function handleArchive(chapter: Chapter) {
    await archiveChapter(storyId, chapter.id);
    setChapters((c) => c.filter((x) => x.id !== chapter.id));
  }

  return (
    <div className="grid grid-cols-1 gap-8 lg:grid-cols-[1fr_18rem]">
      <div>
        {isLoading && (
          <div className="space-y-2">
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
            <Skeleton className="h-12 w-full" />
          </div>
        )}
        {!isLoading && chapters.length === 0 && (
          <EmptyState title="No chapters yet." description="Start one below." />
        )}
        {!isLoading && chapters.length > 0 && (
          <Reorder.Group axis="y" values={chapters} onReorder={handleReorder} className="flex flex-col">
            {chapters.map((chapter) => (
              <ChapterRow
                key={chapter.id}
                storyId={storyId}
                chapter={chapter}
                onRename={(title) => handleRename(chapter, title)}
                onSetTargetLength={(words) => handleSetTargetLength(chapter, words)}
                onToggleLock={() => handleToggleLock(chapter)}
                onArchive={() => handleArchive(chapter)}
              />
            ))}
          </Reorder.Group>
        )}
        <AddChapterRow onAdd={handleAdd} />
      </div>

      <aside className="flex flex-col gap-6">
        <div>
          <h2 className="font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">Story bible</h2>
          <dl className="mt-2 space-y-1.5">
            {story.tone && <BibleFact label="Tone" value={story.tone} />}
            {story.pov && <BibleFact label="POV" value={story.pov.replace("_", " ")} />}
            {story.themes && story.themes.length > 0 && <BibleFact label="Themes" value={story.themes.join(" · ")} />}
            {story.content_boundaries && <BibleFact label="Boundaries" value={story.content_boundaries} />}
          </dl>
        </div>
        <div>
          <h2 className="font-mono text-xs font-medium uppercase tracking-wide text-muted-foreground">Active cast</h2>
          <div className="mt-2 flex flex-col gap-2">
            {story.characters.length === 0 && <p className="text-sm text-muted-foreground">None imported yet.</p>}
            {story.characters.map((c) => (
              <div key={c.id} className="flex items-center gap-2">
                <Monogram seed={c.id} label={c.name} size="sm" />
                <span className="text-sm">{c.name}</span>
              </div>
            ))}
          </div>
        </div>
      </aside>
    </div>
  );
}

function BibleFact({ label, value }: { label: string; value: string }) {
  return (
    <div className="text-sm">
      <dt className="inline font-medium">{label}</dt> <dd className="inline text-muted-foreground">{value}</dd>
    </div>
  );
}
