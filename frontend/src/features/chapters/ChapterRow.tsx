import { useState, type KeyboardEvent } from "react";
import { Link } from "react-router-dom";
import { Reorder, useDragControls } from "motion/react";
import { GripVertical, Lock, MoreHorizontal } from "lucide-react";
import { cn } from "@/lib/utils";
import { StatusPill } from "@/components/StatusPill";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import type { Chapter } from "@/lib/types";

export function ChapterRow({
  storyId,
  chapter,
  onRename,
  onSetTargetLength,
  onToggleLock,
  onArchive,
}: {
  storyId: string;
  chapter: Chapter;
  onRename: (title: string) => void;
  onSetTargetLength: (words: number | null) => void;
  onToggleLock: () => void;
  onArchive: () => void;
}) {
  const controls = useDragControls();
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState(chapter.title ?? "");
  const [targetDraft, setTargetDraft] = useState(String(chapter.target_length_words ?? ""));
  const [confirmArchive, setConfirmArchive] = useState(false);

  function commitRename() {
    setRenaming(false);
    const next = titleDraft.trim();
    if (next !== (chapter.title ?? "")) onRename(next);
  }

  function handleTitleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") e.currentTarget.blur();
    if (e.key === "Escape") setRenaming(false);
  }

  return (
    <Reorder.Item
      value={chapter}
      dragListener={false}
      dragControls={controls}
      className="group flex items-center gap-3 rounded-md border-l-2 border-transparent bg-transparent px-2 py-2.5 transition-colors hover:border-primary hover:bg-card"
    >
      <button
        onPointerDown={(e) => controls.start(e)}
        className="-m-3.5 flex size-11 cursor-grab touch-none items-center justify-center text-muted-foreground hover:text-foreground active:cursor-grabbing"
        aria-label="Reorder chapter"
      >
        <GripVertical className="size-4" />
      </button>

      <span className="w-6 shrink-0 font-mono text-xs text-graphite">
        {String(chapter.order_index + 1).padStart(2, "0")}
      </span>

      <div className="min-w-0 flex-1">
        {renaming ? (
          <Input
            autoFocus
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={commitRename}
            onKeyDown={handleTitleKeyDown}
            placeholder="Untitled chapter"
            className="h-7 max-w-xs"
          />
        ) : (
          <Link
            to={`/stories/${storyId}/chapters/${chapter.id}`}
            className={cn(
              "font-display text-sm font-medium",
              !chapter.title && "italic text-graphite",
            )}
          >
            {chapter.title || "Untitled chapter"}
          </Link>
        )}
      </div>

      <StatusPill status={chapter.status} kind="chapter" />
      {chapter.status === "in_review" && (
        <span className="font-mono text-[0.6875rem] uppercase tracking-wide text-marigold">◆ draft waiting</span>
      )}

      <DropdownMenu>
        <DropdownMenuTrigger className="-m-3.5 flex size-11 items-center justify-center text-muted-foreground opacity-0 outline-none transition-opacity group-hover:opacity-100 focus-visible:opacity-100">
          <MoreHorizontal className="size-4" />
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem
            onSelect={() => {
              setTitleDraft(chapter.title ?? "");
              setRenaming(true);
            }}
          >
            Rename
          </DropdownMenuItem>
          <Popover>
            <PopoverTrigger asChild>
              <DropdownMenuItem onSelect={(e) => e.preventDefault()}>Set target length</DropdownMenuItem>
            </PopoverTrigger>
            <PopoverContent className="flex w-56 gap-2" align="start">
              <Input
                type="number"
                value={targetDraft}
                onChange={(e) => setTargetDraft(e.target.value)}
                placeholder="words"
              />
              <Button size="sm" onClick={() => onSetTargetLength(targetDraft ? Number(targetDraft) : null)}>
                Save
              </Button>
            </PopoverContent>
          </Popover>
          <DropdownMenuItem onSelect={onToggleLock}>
            <Lock /> {chapter.status === "locked" ? "Unlock" : "Lock"}
          </DropdownMenuItem>
          <DropdownMenuItem variant="destructive" onSelect={() => setConfirmArchive(true)}>
            Archive
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <AlertDialog open={confirmArchive} onOpenChange={setConfirmArchive}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Archive this chapter?</AlertDialogTitle>
            <AlertDialogDescription>It leaves the list. Your accepted text is kept.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={onArchive}>Archive</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Reorder.Item>
  );
}
