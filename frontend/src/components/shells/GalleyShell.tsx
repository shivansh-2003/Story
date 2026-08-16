import type { ReactNode } from "react";

// The writing room is a focus surface — no top nav, full-bleed. The chapter's
// own rail (back link, title, status) lives in the galley page itself; a
// dedicated rail component lands with the Phase 4 galley rebuild.
export function GalleyShell({ children }: { children: ReactNode }) {
  return <div className="min-h-full bg-background">{children}</div>;
}
