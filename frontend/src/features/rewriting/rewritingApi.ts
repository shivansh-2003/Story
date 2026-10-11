import { apiFetch } from "@/lib/apiFetch";
import type { UUID } from "@/lib/types";

export type TextSelection = { start: number; end: number; original_text: string };
export type RewriteProposal = TextSelection & {
  id: UUID; turn_id: UUID; base_turn_version: number;
  base_manuscript_revision: number; context_version: string;
  proposed_text: string | null; instruction: string;
  status: "generating" | "ready" | "failed" | "cancelled" | "applied";
  applied_version: number | null; created_at: string; expires_at: string;
};
export type ApplyReceipt = {
  proposal_id: UUID; applied_version: number; applied_content: string; already_applied: boolean;
};
const base = (story: UUID, chapter: UUID, turn: UUID) =>
  `/stories/${story}/chapters/${chapter}/turns/${turn}/rewrite-proposals`;
export const generateRewrite = (story: UUID, chapter: UUID, turn: UUID, body: TextSelection & { proposal_id: UUID; expected_version: number; instruction: string }) =>
  apiFetch<RewriteProposal>(base(story, chapter, turn), { method: "POST", body });
export const listRewrites = (story: UUID, chapter: UUID, turn: UUID) =>
  apiFetch<RewriteProposal[]>(base(story, chapter, turn));
export const getRewrite = (story: UUID, chapter: UUID, turn: UUID, id: UUID) =>
  apiFetch<RewriteProposal>(`${base(story, chapter, turn)}/${id}`);
export const applyRewrite = (story: UUID, chapter: UUID, turn: UUID, id: UUID) =>
  apiFetch<ApplyReceipt>(`${base(story, chapter, turn)}/${id}/apply`, { method: "POST" });
export const cancelRewrite = (story: UUID, chapter: UUID, turn: UUID, id: UUID) =>
  apiFetch<RewriteProposal>(`${base(story, chapter, turn)}/${id}/cancel`, { method: "POST" });
