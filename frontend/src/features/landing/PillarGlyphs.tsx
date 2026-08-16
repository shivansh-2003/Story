import { animate, svg } from "animejs";
import { useAnimeScope } from "@/hooks/useAnimeScope";
import { prefersReducedMotion } from "@/lib/motion";

type Variant = "continuity" | "control" | "iteration";

// Hand-drawn line marks, not icon-library glyphs — stroke-drawn via
// animejs's SVG module so each sketches itself in rather than popping in.
const PATHS: Record<Variant, string> = {
  continuity: "M14 2 L26 14 L14 26 L2 14 Z M14 10 L14 10.1",
  control: "M14 3 L24 14 L14 25 L4 14 Z M9 14 L12.5 17.5 L19 10",
  iteration: "M21.5 8.5 A9 9 0 1 1 14 5 M21.5 3 L21.5 8.5 L16 8.5",
};

export function PillarGlyph({ variant, trigger }: { variant: Variant; trigger: boolean }) {
  const scope = useAnimeScope<SVGSVGElement>(() => {
    if (prefersReducedMotion() || !trigger) return;
    const drawables = svg.createDrawable("path");
    animate(drawables, { draw: ["0 0", "0 1"], duration: 680, delay: 80, ease: "outQuint" });
  }, [trigger]);

  return (
    <svg ref={scope} width="28" height="28" viewBox="0 0 28 28" fill="none">
      <path
        d={PATHS[variant]}
        stroke="rgb(var(--nonrepro))"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
