import { useEffect, useRef, useState } from "react";
import { createHeroScene } from "./heroScene";
import { HeroPoster } from "./HeroPoster";

// The only file that imports three.js — React.lazy()'d from LandingPage so
// the chunk never reaches a protected route.
export default function HeroCanvas() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    const canvas = canvasRef.current;
    const container = containerRef.current;
    if (!canvas || !container) return;

    let scene: ReturnType<typeof createHeroScene>;
    try {
      scene = createHeroScene(canvas);
    } catch {
      setFailed(true);
      return;
    }

    let raf = 0;
    let start = performance.now();
    let intersecting = true;
    let hidden = document.hidden;
    let wasRunning = true;
    let pausedAt = 0;

    function tick(now: number) {
      const running = intersecting && !hidden;
      // Re-baseline on resume: without this, tabbing away for a while and
      // coming back would make the loop's elapsed-time clock jump forward
      // by the paused duration, cutting instantly to some arbitrary later
      // point in the 9s cycle instead of continuing smoothly.
      if (running && !wasRunning) start += now - pausedAt;
      if (!running && wasRunning) pausedAt = now;
      wasRunning = running;
      if (running) scene.frame(now - start);
      raf = requestAnimationFrame(tick);
    }
    raf = requestAnimationFrame(tick);

    function handleResize() {
      const rect = container!.getBoundingClientRect();
      scene.resize(rect.width, rect.height);
    }
    handleResize();
    const ro = new ResizeObserver(handleResize);
    ro.observe(container);

    function handlePointerMove(e: PointerEvent) {
      const rect = container!.getBoundingClientRect();
      scene.setPointer(((e.clientX - rect.left) / rect.width) * 2 - 1, ((e.clientY - rect.top) / rect.height) * 2 - 1);
    }
    container.addEventListener("pointermove", handlePointerMove);

    const io = new IntersectionObserver(([entry]) => (intersecting = entry.isIntersecting), { threshold: 0.05 });
    io.observe(container);

    function handleVisibility() {
      hidden = document.hidden;
    }
    document.addEventListener("visibilitychange", handleVisibility);

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      io.disconnect();
      container.removeEventListener("pointermove", handlePointerMove);
      document.removeEventListener("visibilitychange", handleVisibility);
      scene.dispose();
    };
  }, []);

  if (failed) return <HeroPoster />;

  return (
    <div ref={containerRef} className="relative h-full w-full">
      <canvas ref={canvasRef} className="h-full w-full" style={{ cursor: "crosshair" }} />
      {/* grain — CSS, not a WebGL pass, same reasoning as the galley sheet's
          own paper texture: a static, barely-visible noise layer isn't
          worth a fragment shader's worth of GPU cost. */}
      <div
        className="pointer-events-none absolute inset-0 opacity-[0.025] mix-blend-overlay"
        style={{
          backgroundImage:
            "url(\"data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='128' height='128'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)'/%3E%3C/svg%3E\")",
        }}
      />
    </div>
  );
}
