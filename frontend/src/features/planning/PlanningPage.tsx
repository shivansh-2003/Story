import { useState } from "react";
import { Link, useOutletContext, useParams, useSearchParams } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { listChapters } from "@/features/chapters/chaptersApi";
import type { StoryOutletContext } from "@/features/stories/StoryLayout";
import type { Chapter, Character } from "@/lib/types";
import * as api from "./planningApi";
import { PlanInputs, SceneInputs } from "./PlanningFields";

export function PlanningPage() {
  const {story} = useOutletContext<StoryOutletContext>();
  const {storyId=""} = useParams();
  const [search,setSearch] = useSearchParams();
  const chapters = useQuery({queryKey:["chapters",storyId],queryFn:()=>listChapters(storyId)});
  const selected = chapters.data?.find(c=>c.id===search.get("chapter")) ?? chapters.data?.[0];
  return <div className="space-y-5">
    <div><h2 className="font-display text-xl">Chapter and scene planning</h2><p className="mt-1 text-sm text-muted-foreground">Planning is optional. Define intended events here, or continue writing directly in the Galley.</p></div>
    {chapters.isLoading && <Skeleton className="h-40 w-full" />}
    {chapters.isError && <p role="alert">{chapters.error.message}</p>}
    {chapters.data?.length===0 && <p>Add a chapter in the Chapters tab to start planning.</p>}
    {selected && <>
      <label className="block max-w-md space-y-1 text-sm">Chapter<select className="block w-full rounded-md border bg-background p-2" value={selected.id} onChange={e=>setSearch({chapter:e.target.value})}>{chapters.data?.map(c=><option key={c.id} value={c.id}>{c.title || "Untitled chapter"}</option>)}</select></label>
      <ChapterPlanning key={selected.id} storyId={storyId} chapter={selected} characters={story.characters.filter(c=>!c.is_archived)} />
    </>}
  </div>;
}

function ChapterPlanning({storyId,chapter,characters}: {storyId:string; chapter:Chapter; characters:Character[]}) {
  const queryClient = useQueryClient();
  const plan = useQuery({queryKey:["plan",storyId,chapter.id],queryFn:()=>api.getPlan(storyId,chapter.id)});
  const scenes = useQuery({queryKey:["scenes",storyId,chapter.id],queryFn:()=>api.getScenes(storyId,chapter.id)});
  const [adding,setAdding] = useState(false);
  const [newScene,setNewScene] = useState<api.SceneFields>({...api.emptyScene});
  const [instruction,setInstruction] = useState("");
  const [proposal,setProposal] = useState<api.PlanProposal|null>(null);
  const [busy,setBusy] = useState(false);
  const [error,setError] = useState("");
  const [planEpoch,setPlanEpoch] = useState(0);
  const locked = chapter.status==="locked";
  async function refresh() {
    await Promise.all([queryClient.invalidateQueries({queryKey:["plan",storyId,chapter.id]}), queryClient.invalidateQueries({queryKey:["scenes",storyId,chapter.id]})]);
  }
  async function action(fn:()=>Promise<unknown>,success?:()=>void) {
    setBusy(true);setError("");
    try {await fn(); success?.(); await refresh();}
    catch(err) {setError((err as Error).message);}
    finally {setBusy(false);}
  }
  async function move(index:number,direction:number) {
    if (!scenes.data) return;
    const ids = scenes.data.scenes.map(s=>s.id);
    [ids[index],ids[index+direction]]=[ids[index+direction],ids[index]];
    await action(()=>api.reorderScenes(storyId,chapter.id,ids,scenes.data!.planning_revision));
  }
  return <div className="space-y-6">
    <Link className="text-sm underline" to={`/stories/${storyId}/chapters/${chapter.id}`}>Open chapter in the Galley</Link>
    {locked && <p role="status" className="text-sm text-muted-foreground">This chapter is locked. Unlock it in the Galley to change planning.</p>}
    {error && <p role="alert" className="text-sm text-destructive">{error} <button className="underline" onClick={refresh}>Reload latest planning</button></p>}
    {plan.data && <PlanEditor key={`${chapter.id}:${planEpoch}`} storyId={storyId} plan={plan.data} disabled={locked||busy} onSaved={refresh} />}
    {(plan.isError || scenes.isError) && <p role="alert" className="text-sm text-destructive">{plan.error?.message || scenes.error?.message}</p>}
    <section className="space-y-3">
      <h3 className="font-display text-lg">Ordered scenes</h3>
      {scenes.isLoading && <Skeleton className="h-24 w-full" />}
      {scenes.data?.scenes.length===0 && <p className="text-sm text-muted-foreground">No scenes planned. You can write without them.</p>}
      {scenes.data?.scenes.map((scene,index)=><div key={scene.id} className="rounded-md border p-4 space-y-3">
        <div className="flex items-center justify-between gap-2"><span className="text-sm font-medium">Scene {index+1}: {scene.title}</span><div className="flex gap-1">
          <Button variant="ghost" size="sm" aria-label={`Move ${scene.title} up`} disabled={locked||busy||index===0} onClick={()=>move(index,-1)}>↑</Button>
          <Button variant="ghost" size="sm" aria-label={`Move ${scene.title} down`} disabled={locked||busy||index===scenes.data!.scenes.length-1} onClick={()=>move(index,1)}>↓</Button>
        </div></div>
        <SceneEditor storyId={storyId} scene={scene} characters={characters} disabled={locked||busy} onSaved={refresh} />
      </div>)}
      {!adding ? <Button variant="outline" disabled={locked||busy} onClick={()=>setAdding(true)}>Add scene</Button> : <div className="rounded-md border p-4 space-y-3">
        <SceneInputs value={newScene} onChange={setNewScene} disabled={busy||locked} characters={characters} />
        <div className="flex gap-2"><Button disabled={busy||locked||!newScene.title.trim()} onClick={()=>action(()=>api.createScene(storyId,chapter.id,newScene),()=>{setAdding(false);setNewScene({...api.emptyScene});})}>Save new scene</Button><Button variant="outline" disabled={busy} onClick={()=>setAdding(false)}>Cancel</Button></div>
      </div>}
    </section>
    <section className="rounded-md border p-4 space-y-3">
      <h3 className="font-display text-lg">AI planning suggestion</h3>
      <p className="text-sm text-muted-foreground">Ask for ideas, review the proposal, and save it when ready. Suggested scenes are appended to your existing scenes.</p>
      <label className="block space-y-1 text-sm">Planning instruction<textarea className="block w-full rounded-md border bg-background p-2" maxLength={2000} value={instruction} disabled={busy||locked} onChange={e=>setInstruction(e.target.value)} placeholder="Plan a tense lighthouse investigation with three scenes." /></label>
      <Button variant="outline" disabled={busy||locked||!instruction.trim()} onClick={()=>action(async()=>{const result=await api.suggestPlan(storyId,chapter.id,instruction);setProposal(result);})}>{busy ? "Working…" : "Suggest a plan"}</Button>
      {proposal && <div role="region" aria-label="AI planning proposal" className="space-y-4 border-t pt-4">
        <p className="text-sm font-medium">Unsaved proposal — review and edit before saving</p>
        <PlanInputs value={proposal.plan} onChange={next=>setProposal({...proposal,plan:next})} disabled={busy||locked} />
        {proposal.scenes.map((scene,index)=><div key={index} className="rounded-md border p-3 space-y-2">
          <SceneInputs value={scene} onChange={next=>setProposal({...proposal,scenes:proposal.scenes.map((s,i)=>i===index ? next : s)})} disabled={busy||locked} characters={characters} />
          <Button variant="ghost" disabled={busy||locked} onClick={()=>setProposal({...proposal,scenes:proposal.scenes.filter((_,i)=>i!==index)})}>Exclude suggested scene {index+1}</Button>
        </div>)}
        <div className="flex gap-2"><Button disabled={busy||locked||proposal.scenes.some(s=>!s.title.trim())} onClick={()=>action(async()=>{const saved=await api.saveProposal(storyId,proposal);queryClient.setQueryData(["plan",storyId,chapter.id],saved);},()=>{setProposal(null);setPlanEpoch(epoch=>epoch+1);toast.success("Plan and suggested scenes saved.");})}>Save suggested plan and scenes</Button><Button variant="outline" disabled={busy} onClick={()=>setProposal(null)}>Discard proposal</Button></div>
      </div>}
    </section>
  </div>;
}

function PlanEditor({storyId,plan,disabled,onSaved}: {storyId:string;plan:api.ChapterPlan;disabled:boolean;onSaved:()=>Promise<void>}) {
  const [fields,setFields] = useState<api.PlanFields>({objective:plan.objective,conflict:plan.conflict,ending_beat:plan.ending_beat,notes:plan.notes});
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [version,setVersion]=useState(plan.version);
  return <section aria-label="Saved chapter plan" className="space-y-3"><h3 className="font-display text-lg">Chapter plan</h3>
    <PlanInputs value={fields} onChange={setFields} disabled={disabled||busy} />
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <div className="flex flex-wrap gap-2"><Button disabled={disabled||busy} onClick={async()=>{setBusy(true);setError("");try{const updated=await api.savePlan(storyId,plan.chapter_id,fields,version);setVersion(updated.version);await onSaved();toast.success("Chapter plan saved.");}catch(err){setError((err as Error).message);}finally{setBusy(false);}}}>{busy ? "Saving…" : "Save chapter plan"}</Button>
      <Button variant="outline" disabled={disabled||busy} onClick={async()=>{setBusy(true);setError("");try{const latest=await api.getPlan(storyId,plan.chapter_id);setFields({objective:latest.objective,conflict:latest.conflict,ending_beat:latest.ending_beat,notes:latest.notes});setVersion(latest.version);}catch(err){setError((err as Error).message);}finally{setBusy(false);}}}>Load latest plan</Button></div>
  </section>;
}

function SceneEditor({storyId,scene,characters,disabled,onSaved}: {storyId:string;scene:api.Scene;characters:Character[];disabled:boolean;onSaved:()=>Promise<void>}) {
  const [fields,setFields]=useState(()=>api.sceneFields(scene));
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState("");
  const [removing,setRemoving]=useState(false);
  const [current,setCurrent]=useState(scene);
  async function action(fn:()=>Promise<unknown>) {setBusy(true);setError("");try{await fn();await onSaved();}catch(err){setError((err as Error).message);}finally{setBusy(false);}}
  return <details><summary className="cursor-pointer text-sm text-muted-foreground">Edit scene details and cast</summary><div className="mt-3 space-y-3">
    <SceneInputs value={fields} onChange={setFields} disabled={disabled||busy} characters={characters} />
    {error && <p role="alert" className="text-sm text-destructive">{error}</p>}
    <div className="flex flex-wrap gap-2"><Button disabled={disabled||busy||!fields.title.trim()} onClick={()=>action(async()=>{const saved=await api.saveScene(storyId,scene.chapter_id,current,fields);setCurrent(saved);})}>Save scene</Button><Button variant="outline" disabled={disabled||busy} onClick={()=>action(async()=>{const latest=(await api.getScenes(storyId,scene.chapter_id)).scenes.find(s=>s.id===scene.id);if(!latest)throw new Error("This scene was removed. Reload planning.");setCurrent(latest);setFields(api.sceneFields(latest));})}>Load latest scene</Button><Button variant="outline" disabled={disabled||busy} onClick={()=>setRemoving(!removing)}>Remove scene</Button></div>
    {removing && <div className="space-y-2 text-sm"><p>Remove this scene from planning? Accepted writing and its scene links remain saved.</p><Button variant="destructive" disabled={disabled||busy} onClick={()=>action(()=>api.removeScene(storyId,scene.chapter_id,current))}>Confirm remove scene</Button></div>}
  </div></details>;
}
