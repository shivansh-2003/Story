import { apiFetch } from "@/lib/apiFetch";

export type PreviewChapter = { index: number; title: string; paragraphs: string[] };
export type ImportPreview = {
  preview_token: string;
  expires_at: string;
  chapters: PreviewChapter[];
  paragraph_count: number;
};
export type ImportMapping = { source_index: number; title: string };
export type ImportCommit = {
  preview_token: string; commit_key: string; chapters: ImportMapping[]; enrich_with_ai: boolean;
};
export type ImportResult = {
  chapters: { id: string; title: string; paragraph_count: number }[];
  paragraph_count: number;
  ai_enrichment_requested: boolean;
};

export function previewImport(storyId: string, file: File) {
  const body = new FormData();
  body.append("file", file);
  return apiFetch<ImportPreview>(`/stories/${storyId}/imports/preview`, { method: "POST", body });
}

export const commitImport = (storyId: string, body: ImportCommit) =>
  apiFetch<ImportResult>(`/stories/${storyId}/imports/commit`, { method: "POST", body });

export const cancelImport = (storyId: string, token: string) =>
  apiFetch<void>(`/stories/${storyId}/imports/preview/${token}`, { method: "DELETE" });

export async function downloadManuscript(storyId: string, title: string, format: "txt" | "md", includeArchived: boolean) {
  const blob = await apiFetch<Blob>(`/stories/${storyId}/export`, {
    query: { format, include_archived: String(includeArchived) }, responseType: "blob",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = `${title.replace(/[^a-zA-Z0-9_-]+/g, "-").replace(/^-|-$/g, "").slice(0, 80) || "manuscript"}.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
