// Static fallback for reduced-motion, coarse-pointer/narrow viewports, and
// WebGL failures. The design spec calls for a build-time WebP render of the
// three.js scene; that needs a headless-render pipeline this pass didn't
// budget for, so this is a CSS approximation of the same beat instead —
// paper on a light table, one line mid-way through settling to ink.
export function HeroPoster() {
  return (
    <div className="flex h-full w-full items-center justify-center rounded-xl bg-[radial-gradient(ellipse_at_40%_30%,rgb(var(--stock))_0%,rgb(var(--well))_75%)] p-10">
      <div className="w-full max-w-md rounded-lg bg-sheet p-8 shadow-[var(--shadow-sheet)]">
        <p className="font-manuscript text-lg leading-relaxed">
          <span style={{ color: "rgb(var(--sheet-foreground))" }}>Nothing the AI writes is </span>
          <span style={{ color: "rgb(var(--pending))" }}>final until you say so.</span>
        </p>
      </div>
    </div>
  );
}
