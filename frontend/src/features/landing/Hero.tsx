import { lazy, Suspense, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { createTimeline, stagger, utils } from "animejs";
import { Button } from "@/components/ui/button";
import { useAnimeScope } from "@/hooks/useAnimeScope";
import { prefersReducedMotion } from "@/lib/motion";
import { HeroPoster } from "./HeroPoster";

const HeroCanvas = lazy(() => import("./HeroCanvas"));

function useHeroSupported() {
  const [supported, setSupported] = useState(false);
  useEffect(() => {
    const reducedMotion = matchMedia("(prefers-reduced-motion: reduce)").matches;
    const coarseAndNarrow = matchMedia("(pointer: coarse)").matches && window.innerWidth < 768;
    const saveData = (navigator as { connection?: { saveData?: boolean } }).connection?.saveData === true;
    setSupported(!reducedMotion && !coarseAndNarrow && !saveData);
  }, []);
  return supported;
}

// The full hero load sequence, ~2.1s, orchestrated as one anime.js timeline
// so the order (text argues, canvas proves, FINAL sweep ties them together)
// stays a single authored moment instead of scattered independent effects.
function useHeroSequence() {
  return useAnimeScope(() => {
    if (prefersReducedMotion()) {
      utils.set("[data-hero-fade]", { opacity: 1, y: 0 });
      utils.set("[data-final-word]", { "--sweep": "100%" });
      return;
    }

    createTimeline({ defaults: { ease: "outExpo" } })
      .add("[data-hero-eyebrow]", { opacity: [0, 1], y: [8, 0], duration: 280 }, 0)
      .add("[data-headline-word]", { opacity: [0, 1], y: [18, 0], duration: 500, delay: stagger(60) }, 120)
      .add("[data-hero-sub]", { opacity: [0, 1], y: [10, 0], duration: 320 }, 640)
      .add("[data-hero-cta]", { opacity: [0, 1], y: [10, 0], duration: 280, delay: stagger(60) }, 780)
      .add(
        "[data-final-word]",
        { "--sweep": ["0%", "100%"], duration: 620, ease: "cubicBezier(.16,.84,.3,1)" },
        1100,
      );
  }, []);
}

export function Hero() {
  const heroSupported = useHeroSupported();
  const scope = useHeroSequence();
  const words = ["Nothing the AI", "writes is", "final", "until you say so."];

  return (
    <section ref={scope} className="relative overflow-hidden pt-16">
      <div className="mx-auto grid max-w-[1200px] grid-cols-1 items-center gap-10 px-6 pt-16 md:grid-cols-[55%_45%] md:pt-24">
        <div className="order-2 md:order-1">
          <p data-hero-fade data-hero-eyebrow className="font-mono text-xs uppercase tracking-[0.14em] text-primary opacity-0">
            A co-writer that asks first
          </p>
          <h1 className="mt-4 font-display text-[clamp(2.5rem,6vw,4.25rem)] font-medium leading-[0.98] tracking-tight">
            {words.map((word, i) => (
              <span key={i} data-headline-word className="mr-[0.28em] inline-block opacity-0">
                {word === "final" ? (
                  <span data-final-word className="ink-sweep">
                    {word}
                  </span>
                ) : (
                  word
                )}
              </span>
            ))}
          </h1>
          <p data-hero-fade data-hero-sub className="mt-6 max-w-[46ch] text-base text-muted-foreground opacity-0">
            Co-write fiction one paragraph at a time. Drafts arrive in blue. You decide what sets in ink.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            <Button data-hero-fade data-hero-cta size="lg" className="opacity-0" asChild>
              <Link to="/signup">Start writing</Link>
            </Button>
            <Button data-hero-fade data-hero-cta size="lg" variant="ghost" className="opacity-0" asChild>
              <a
                href="#loop"
                onClick={(e) => {
                  e.preventDefault();
                  document.getElementById("loop")?.scrollIntoView({ behavior: "smooth", block: "start" });
                }}
              >
                See how it works ↓
              </a>
            </Button>
          </div>
        </div>

        <div className="order-1 aspect-[4/3] w-full md:order-2" style={{ cursor: heroSupported ? "crosshair" : undefined }}>
          {heroSupported ? (
            <Suspense fallback={<HeroPoster />}>
              <HeroCanvas />
            </Suspense>
          ) : (
            <HeroPoster />
          )}
        </div>
      </div>

      <ScrollCue />
    </section>
  );
}

function ScrollCue() {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    function onScroll() {
      setVisible(window.scrollY <= 80);
    }
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  if (!visible) return null;

  return (
    <div className="hidden justify-center pb-8 md:flex">
      <div className="flex flex-col items-center gap-2 font-mono text-[0.6875rem] uppercase tracking-[0.14em] text-muted-foreground">
        <span>Scroll</span>
        <div className="relative h-3 w-px bg-graphite/40">
          <span className="absolute -left-[3px] top-0 size-[7px] animate-bounce rounded-full bg-primary" />
        </div>
      </div>
    </div>
  );
}
