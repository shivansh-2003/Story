import { apiFetch } from "@/lib/apiFetch";

export type PlanFields = { objective: string; conflict: string; ending_beat: string; notes: string };
export type ChapterPlan = PlanFields & { chapter_id: string; version: number; planning_revision: number };
export type SceneFields = {
  title: string; goal: string; conflict: string; outcome: string; setting: string; notes: string;
  pov_character_id: string | null; character_ids: string[];
};
export type Scene = SceneFields & { id: string; chapter_id: string; order_index: number; version: number; updated_at: string };
export type SceneList = { scenes: Scene[]; planning_revision: number };
export type PlanProposal = {
  chapter_id: string; expected_plan_version: number; expected_planning_revision: number; expected_manuscript_revision: number;
  plan: PlanFields; scenes: SceneFields[];
};
const base = (story: string, chapter: string) => `/stories/${story}/chapters/${chapter}`;
export const getPlan = (story: string, chapter: string) => apiFetch<ChapterPlan>(`${base(story, chapter)}/plan`);
export const savePlan = (story: string, chapter: string, fields: PlanFields, expected_version: number) =>
  apiFetch<ChapterPlan>(`${base(story, chapter)}/plan`, { method: "PATCH", body: {...fields, expected_version} });
export const getScenes = (story: string, chapter: string) => apiFetch<SceneList>(`${base(story, chapter)}/scenes`);
export const createScene = (story: string, chapter: string, fields: SceneFields) =>
  apiFetch<Scene>(`${base(story, chapter)}/scenes`, {method:"POST", body:fields});
export const saveScene = (story: string, chapter: string, scene: Scene, fields: SceneFields) =>
  apiFetch<Scene>(`${base(story, chapter)}/scenes/${scene.id}`, {method:"PATCH", body:{...fields, expected_version:scene.version}});
export const removeScene = (story: string, chapter: string, scene: Scene) =>
  apiFetch<void>(`${base(story, chapter)}/scenes/${scene.id}`, {method:"DELETE", query:{expected_version:String(scene.version)}});
export const reorderScenes = (story: string, chapter: string, scene_ids: string[], expected_planning_revision: number) =>
  apiFetch<void>(`${base(story, chapter)}/scenes/reorder`, {method:"PATCH", body:{scene_ids, expected_planning_revision}});
export const suggestPlan = (story: string, chapter_id: string, instruction: string) =>
  apiFetch<PlanProposal>(`/stories/${story}/plan-suggestions`, {method:"POST", body:{chapter_id,instruction}});
export const saveProposal = (story: string, proposal: PlanProposal) => {
  const {chapter_id, ...body} = proposal;
  return apiFetch<ChapterPlan>(`${base(story,chapter_id)}/plan-proposals/save`, {method:"POST", body});
};

export const emptyPlan: PlanFields = { objective:"", conflict:"", ending_beat:"", notes:"" };
export const emptyScene: SceneFields = { title:"", goal:"", conflict:"", outcome:"", setting:"", notes:"", pov_character_id:null, character_ids:[] };

export function sceneFields(scene: SceneFields): SceneFields {
  return Object.fromEntries(Object.keys(emptyScene).map(key => [key, scene[key as keyof SceneFields]])) as SceneFields;
}
