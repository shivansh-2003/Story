import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, Lock, MoreHorizontal, Unlock } from "lucide-react";
import {
  createAndActivateCharacter,
  getChapter,
  lockChapter,
  unlockChapter,
  updateChapter,
} from "@/features/chapters/chaptersApi";
import { StatusPill } from "@/components/StatusPill";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useKeyboardMap } from "@/hooks/useKeyboardMap";
import { Sheet } from "./Sheet";
import { AttemptsRail } from "./AttemptsRail";
import { InSceneRail } from "./InSceneRail";
import { InstructionConsole } from "./InstructionConsole";
import { useChapterSession } from "./useChapterSession";
import { useDebouncedManualEdit } from "./useDebouncedManualEdit";

type Length = "short" | "standard" | "long";

export function GalleyPage() {
  const { storyId = "", chapterId = "" } = useParams();
  const queryClient = useQueryClient();
  const {
    state,
    hydrate,
    doGenerate,
    doEditInstruction,
    doManualEdit,
    doAccept,
    doDiscard,
    restoreSibling,
    doComplete,
    stopGenerating,
  } = useChapterSession(storyId, chapterId);

  // The only fetch of this chapter — useChapterSession used to fetch it a
  // second time itself (see hydrate()'s comment), doubling the request and
  // the three sequential DB round trips behind it on every chapter open.
  const { data: chapter } = useQuery({ queryKey: ["chapter", storyId, chapterId], queryFn: () => getChapter(storyId, chapterId) });
  const syncManualEdit = useDebouncedManualEdit(storyId, chapterId, doManualEdit);

  const [instruction, setInstruction] = useState("");
  const [length, setLength] = useState<Length>("standard");
  const [editing, setEditing] = useState(false);
  const [justAcceptedIndex, setJustAcceptedIndex] = useState<number | null>(null);
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [addCharacterBusy, setAddCharacterBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  const hydratedFor = useRef<string | null>(null);
  useEffect(() => {
    if (!chapter || hydratedFor.current === chapterId) return;
    hydratedFor.current = chapterId;
    hydrate(chapter);
  }, [chapter, chapterId, hydrate]);

  const isBusy = state.status === "generating" || state.status === "accepting" || state.status === "completing";
  const streaming = state.status === "generating";
  const locked = chapter?.status === "locked";

  const rename = useMutation({
    mutationFn: (title: string) => updateChapter(storyId, chapterId, { title: title || null }),
    onSuccess: (updated) => queryClient.setQueryData(["chapter", storyId, chapterId], (prev: typeof chapter) => ({ ...prev!, ...updated })),
  });

  const toggleLock = useMutation({
    mutationFn: () => (locked ? unlockChapter(storyId, chapterId) : lockChapter(storyId, chapterId)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["chapter", storyId, chapterId] }),
  });

  async function handleAccept() {
    const acceptedIndex = state.acceptedParagraphs.length;
    await doAccept();
    setJustAcceptedIndex(acceptedIndex);
    setTimeout(() => setJustAcceptedIndex(null), 900);
  }

  async function handleComplete() {
    const completed = await doComplete();
    if (completed) queryClient.invalidateQueries({ queryKey: ["chapter", storyId, chapterId] });
  }

  function commitRename() {
    setRenaming(false);
    const next = titleDraft.trim();
    if (chapter && next !== (chapter.title ?? "")) rename.mutate(next);
  }

  async function handleAddCharacter(name: string, role: string) {
    setAddCharacterBusy(true);
    try {
      const character = await createAndActivateCharacter(storyId, chapterId, { name, role: role || null });
      setInstruction((prev) => (prev.trim() ? `${prev.trim()} ${character.name} enters the scene.` : `${character.name} enters the scene.`));
      setNotice(`${character.name} joins from your next generation. The draft on the page is unchanged.`);
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setAddCharacterBusy(false);
    }
  }

  useKeyboardMap(
    {
      "mod+Enter": () => {
        if (state.pendingTurn) return;
        if (instruction.trim()) doGenerate(instruction, length);
      },
      "mod+k": () => state.pendingTurn && !isBusy && handleAccept(),
      "mod+e": () => state.pendingTurn && !isBusy && setEditing(true),
      "mod+Backspace": () => state.pendingTurn && !isBusy && doDiscard(),
      Escape: () => (editing ? setEditing(false) : stopGenerating()),
    },
    !!chapter,
  );

  if (!chapter) {
    return (
      <div className="mx-auto max-w-6xl space-y-4 px-6 py-6">
        <Skeleton className="h-8 w-64" />
        <Skeleton className="h-96 w-full" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-6xl px-6 py-6">
      <div className="flex items-center gap-3">
        <Link
          to={`/stories/${storyId}/chapters`}
          className="-m-3 flex size-11 items-center justify-center text-muted-foreground hover:text-foreground"
        >
          <ChevronLeft className="size-5" />
        </Link>
        {renaming ? (
          <Input
            autoFocus
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={commitRename}
            onKeyDown={(e) => {
              if (e.key === "Enter") e.currentTarget.blur();
              if (e.key === "Escape") setRenaming(false);
            }}
            className="h-8 max-w-xs"
          />
        ) : (
          <h1
            className="cursor-pointer font-display text-lg font-medium"
            onClick={() => {
              setTitleDraft(chapter.title ?? "");
              setRenaming(true);
            }}
          >
            {chapter.title || "Untitled chapter"}
          </h1>
        )}
        <StatusPill status={chapter.status} kind="chapter" />
        {locked ? <Lock className="size-4 text-muted-foreground" /> : <Unlock className="size-4 text-muted-foreground" />}

        <div className="ml-auto">
          <DropdownMenu>
            <DropdownMenuTrigger className="-m-3 flex size-11 items-center justify-center text-muted-foreground outline-none">
              <MoreHorizontal className="size-5" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {state.pendingTurn ? (
                <DropdownMenuItem disabled title="Resolve the draft on the page first — keep it or throw it away.">
                  Complete chapter
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem onSelect={handleComplete} disabled={isBusy}>
                  Complete chapter
                </DropdownMenuItem>
              )}
              <DropdownMenuItem onSelect={() => toggleLock.mutate()}>{locked ? "Unlock" : "Lock"}</DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[12rem_1fr_10rem]">
        <InSceneRail onAdd={handleAddCharacter} busy={addCharacterBusy} />

        <div className={chapter.status === "complete" ? "opacity-60" : undefined}>
          <Sheet
            paragraphs={state.acceptedParagraphs}
            justAcceptedIndex={justAcceptedIndex}
            pendingTurn={state.pendingTurn}
            streaming={streaming}
            editing={editing}
            busy={isBusy}
            onManualEdit={syncManualEdit}
            onEditSave={(content) => {
              syncManualEdit(content);
              setEditing(false);
            }}
            onEditCancel={() => setEditing(false)}
            onKeep={handleAccept}
            onRewrite={doEditInstruction}
            onEdit={() => setEditing(true)}
            onDiscard={doDiscard}
          />

          {notice && <p className="mt-3 text-sm text-marigold">{notice}</p>}
          {state.errorMessage && <p className="mt-3 text-sm text-destructive">{state.errorMessage}</p>}

          <InstructionConsole
            instruction={instruction}
            onInstructionChange={setInstruction}
            length={length}
            onLengthChange={setLength}
            generating={streaming}
            locked={locked}
            onUnlock={() => toggleLock.mutate()}
            onSubmit={() => instruction.trim() && !state.pendingTurn && doGenerate(instruction, length)}
            onStop={stopGenerating}
          />
        </div>

        <AttemptsRail attempts={state.siblingAttempts} onRestore={restoreSibling} />
      </div>
    </div>
  );
}
