import { useEffect, useState } from "react";
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
import { getMemoryStatus, refreshMemory } from "./generationApi";
import { getScenes } from "@/features/planning/planningApi";

type Length = "short" | "standard" | "long";

export function GalleyPage() {
  const { storyId = "", chapterId = "" } = useParams();
  const queryClient = useQueryClient();
  const {
    state,
    hydrate,
    updateAccepted,
    reloadSession,
    doGenerate,
    doEditInstruction,
    saveManualEdit,
    doAccept,
    doDiscard,
    restoreSibling,
    doComplete,
    stopGenerating,
  } = useChapterSession(storyId, chapterId);

  // The only fetch of this chapter — useChapterSession used to fetch it a
  // second time itself (see hydrate()'s comment), doubling the request and
  // the three sequential DB round trips behind it on every chapter open.
  const { data: chapter } = useQuery({
    queryKey: ["chapter", storyId, chapterId],
    queryFn: () => getChapter(storyId, chapterId),
  });
  const memory = useQuery({
    queryKey: ["chapter-memory", storyId, chapterId],
    queryFn: () => getMemoryStatus(storyId, chapterId),
    refetchInterval: (query) =>
      ["queued", "running"].includes(query.state.data?.status ?? "")
        ? 5000
        : false,
  });

  const [instruction, setInstruction] = useState("");
  const [selectedScene, setSelectedScene] = useState<{chapterId:string; id:string}>({chapterId, id:""});
  const scenes = useQuery({queryKey:["scenes",storyId,chapterId],queryFn:()=>getScenes(storyId,chapterId)});
  const sceneId = selectedScene.chapterId === chapterId && scenes.data?.scenes.some(s=>s.id===selectedScene.id) ? selectedScene.id : null;
  const [length, setLength] = useState<Length>("standard");
  const [editing, setEditing] = useState(false);
  const [justAcceptedIndex, setJustAcceptedIndex] = useState<number | null>(
    null,
  );
  const [renaming, setRenaming] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [addCharacterBusy, setAddCharacterBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    if (!chapter) return;
    hydrate(chapter);
  }, [chapter, chapterId, hydrate]);

  const isBusy =
    !state.ready ||
    ["generating", "accepting", "completing", "saving"].includes(state.status);
  const streaming = state.status === "generating";
  const locked = chapter?.status === "locked";

  const rename = useMutation({
    mutationFn: (title: string) =>
      updateChapter(storyId, chapterId, { title: title || null }),
    onSuccess: (updated) =>
      queryClient.setQueryData(
        ["chapter", storyId, chapterId],
        (prev: typeof chapter) => ({ ...prev!, ...updated }),
      ),
  });

  const toggleLock = useMutation({
    mutationFn: () =>
      locked
        ? unlockChapter(storyId, chapterId)
        : lockChapter(storyId, chapterId),
    onSuccess: () =>
      queryClient.invalidateQueries({
        queryKey: ["chapter", storyId, chapterId],
      }),
  });

  async function handleAccept() {
    const acceptedIndex = state.acceptedParagraphs.length;
    if (await doAccept()) {
      setJustAcceptedIndex(acceptedIndex);
      setTimeout(() => setJustAcceptedIndex(null), 900);
      queryClient.invalidateQueries({
        queryKey: ["chapter", storyId, chapterId],
      });
      queryClient.invalidateQueries({
        queryKey: ["chapter-memory", storyId, chapterId],
      });
    }
  }

  async function handleComplete() {
    const completed = await doComplete();
    if (completed) {
      queryClient.invalidateQueries({
        queryKey: ["chapter", storyId, chapterId],
      });
      queryClient.invalidateQueries({
        queryKey: ["chapter-memory", storyId, chapterId],
      });
    }
  }

  function commitRename() {
    setRenaming(false);
    const next = titleDraft.trim();
    if (chapter && next !== (chapter.title ?? "")) rename.mutate(next);
  }

  async function handleAddCharacter(name: string, role: string) {
    setAddCharacterBusy(true);
    try {
      const character = await createAndActivateCharacter(storyId, chapterId, {
        name,
        role: role || null,
      });
      setInstruction((prev) =>
        prev.trim()
          ? `${prev.trim()} ${character.name} enters the scene.`
          : `${character.name} enters the scene.`,
      );
      setNotice(
        `${character.name} joins from your next generation. The draft on the page is unchanged.`,
      );
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setAddCharacterBusy(false);
    }
  }

  useKeyboardMap(
    {
      "mod+Enter": () => {
        if (state.pendingTurn || locked || isBusy || editing) return;
        if (instruction.trim()) doGenerate(instruction, length, sceneId);
      },
      "mod+k": () =>
        state.pendingTurn && !isBusy && !locked && !editing && handleAccept(),
      "mod+e": () =>
        state.pendingTurn && !isBusy && !locked && setEditing(true),
      "mod+Backspace": () =>
        state.pendingTurn && !isBusy && !locked && !editing && doDiscard(),
      Escape: () => {
        if (editing) {
          setEditing(false);
          void reloadSession();
        } else stopGenerating();
      },
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
        {locked ? (
          <Lock className="size-4 text-muted-foreground" />
        ) : (
          <Unlock className="size-4 text-muted-foreground" />
        )}

        <div className="ml-auto">
          <DropdownMenu>
            <DropdownMenuTrigger className="-m-3 flex size-11 items-center justify-center text-muted-foreground outline-none">
              <MoreHorizontal className="size-5" />
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end">
              {state.pendingTurn ? (
                <DropdownMenuItem
                  disabled
                  title="Resolve the draft on the page first — keep it or throw it away."
                >
                  Complete chapter
                </DropdownMenuItem>
              ) : (
                <DropdownMenuItem
                  onSelect={handleComplete}
                  disabled={isBusy || locked}
                >
                  Complete chapter
                </DropdownMenuItem>
              )}
              <DropdownMenuItem
                disabled={isBusy || editing}
                onSelect={() => toggleLock.mutate()}
              >
                {locked ? "Unlock" : "Lock"}
              </DropdownMenuItem>
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-1 gap-8 lg:grid-cols-[12rem_1fr_10rem]">
        <InSceneRail onAdd={handleAddCharacter} busy={addCharacterBusy} />

        <div
          className={chapter.status === "complete" ? "opacity-60" : undefined}
        >
          <div className="mb-5 space-y-2">
            <label className="block space-y-1 text-sm">Scene for next generation (optional)
              <select className="block w-full rounded-md border bg-background p-2" value={state.pendingTurn ? state.pendingTurn.scene_id ?? "" : sceneId ?? ""}
                disabled={isBusy||editing||locked||!!state.pendingTurn||scenes.isLoading} onChange={e=>setSelectedScene({chapterId,id:e.target.value})}>
                <option value="">No scene — use chapter context and cast</option>
                {state.pendingTurn?.scene_id && !scenes.data?.scenes.some(s=>s.id===state.pendingTurn!.scene_id) && <option value={state.pendingTurn.scene_id}>Scene removed — review this draft</option>}
                {scenes.data?.scenes.map(scene=><option key={scene.id} value={scene.id}>{scene.order_index+1}. {scene.title}</option>)}
              </select>
            </label>
            <Link className="text-sm underline" to={`/stories/${storyId}/planning?chapter=${chapterId}`}>Plan this chapter and its scenes</Link>
            {scenes.isError && <p role="alert" className="text-sm text-destructive">Scene list unavailable. You can continue without a selected scene. <button className="underline" onClick={()=>scenes.refetch()}>Retry</button></p>}
            {state.pendingTurn && <p className="text-xs text-muted-foreground">The pending draft keeps the scene it was generated for. Choose a scene for the next paragraph after resolving it.</p>}
          </div>
          <Sheet
            storyId={storyId}
            chapterId={chapterId}
            locked={locked}
            onAcceptedSaved={updateAccepted}
            paragraphs={state.acceptedParagraphs}
            sceneTitles={Object.fromEntries((scenes.data?.scenes ?? []).map(scene=>[scene.id,scene.title]))}
            justAcceptedIndex={justAcceptedIndex}
            pendingTurn={state.pendingTurn}
            streaming={streaming}
            editing={editing}
            busy={isBusy || locked}
            onEditSave={async (content) => {
              if (await saveManualEdit(content)) setEditing(false);
            }}
            onEditCancel={() => {
              setEditing(false);
              void reloadSession();
            }}
            onKeep={handleAccept}
            onRewrite={doEditInstruction}
            onEdit={() => setEditing(true)}
            onDiscard={doDiscard}
          />

          {notice && <p className="mt-3 text-sm text-marigold">{notice}</p>}
          {state.errorMessage && (
            <p className="mt-3 text-sm text-destructive">
              {state.errorMessage}{" "}
              <button
                className="underline"
                onClick={() =>
                  reloadSession().catch((e: Error) => setNotice(e.message))
                }
              >
                Reload draft
              </button>
            </p>
          )}
          {state.staleDraft && (
            <p role="status" className="mt-3 text-sm text-marigold">
              This draft was written before the manuscript or planning changed. Review and
              save it, or rewrite it, before keeping it.
            </p>
          )}
          {memory.data && !memory.data.fresh && (
            <p role="status" className="mt-3 text-sm text-muted-foreground">
              {memory.data.status === "failed"
                ? "AI memory refresh failed. Your manuscript is saved."
                : memory.data.status === "not_requested"
                ? "AI memory has not been refreshed. New generation uses current manuscript text."
                : "AI memory is updating. New generation uses current manuscript text."}
              {["failed", "not_requested"].includes(memory.data.status) && (
                <button
                  className="ml-2 underline"
                  onClick={async () => {
                    try {
                      await refreshMemory(storyId, chapterId);
                      await memory.refetch();
                    } catch (e) {
                      setNotice((e as Error).message);
                    }
                  }}
                >
                  {memory.data.status === "not_requested" ? "Refresh AI memory" : "Retry memory refresh"}
                </button>
              )}
            </p>
          )}

          <InstructionConsole
            instruction={instruction}
            onInstructionChange={setInstruction}
            length={length}
            onLengthChange={setLength}
            generating={streaming}
            locked={locked}
            onUnlock={() => toggleLock.mutate()}
            disabled={isBusy || editing || !!state.pendingTurn}
            onSubmit={() =>
              instruction.trim() &&
              !state.pendingTurn &&
              !isBusy &&
              !locked &&
              !editing &&
              doGenerate(instruction, length, sceneId)
            }
            onStop={stopGenerating}
          />
        </div>

        <AttemptsRail
          attempts={state.siblingAttempts}
          onRestore={(turn) =>
            !isBusy && !locked && !editing && restoreSibling(turn)
          }
        />
      </div>
    </div>
  );
}
