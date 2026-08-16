import { Link } from "react-router-dom";
import { motion } from "motion/react";
import type { Story } from "@/lib/types";
import { StatusPill } from "@/components/StatusPill";

// The tick-rule progress mark from the design spec needs a per-story chapter
// count, which `GET /stories` doesn't return — fetching it per-card would be
// an N+1 request storm. It lives on the chapter list page instead, where the
// chapters are already loaded.
export function StoryCard({ story }: { story: Story }) {
  return (
    <motion.div whileHover={{ y: -3 }} transition={{ duration: 0.2 }} className="h-full">
      <Link
        to={`/stories/${story.id}/chapters`}
        className="flex h-full flex-col gap-3 rounded-lg border border-border bg-card p-5 shadow-[var(--shadow-raised)] transition-colors hover:border-primary/40"
      >
        <StatusPill status={story.status} kind="story" />
        <h3 className="font-display text-lg font-medium leading-tight line-clamp-3">{story.title}</h3>
        {story.premise && (
          <p className="font-manuscript text-sm italic leading-snug text-muted-foreground line-clamp-2">
            "{story.premise}"
          </p>
        )}
        <div className="mt-auto pt-2">
          {story.genre?.length ? (
            <span className="font-mono text-xs text-muted-foreground">{story.genre.join(" · ")}</span>
          ) : null}
        </div>
      </Link>
    </motion.div>
  );
}
