import { useRef } from "react";
import { motion, useInView, useScroll, useTransform } from "motion/react";
import { cn } from "@/lib/utils";
import { LoopConnector } from "./LoopConnector";
import styles from "./landing.module.css";

const STEPS = [
  { n: "01", caption: "Tell it what happens next.", sub: "You write an instruction, not a whole scene." },
  {
    n: "02",
    caption: "Watch it write, word by word.",
    sub: "Generation streams in — you can tell in a sentence whether it's working.",
  },
  {
    n: "03",
    caption: "Read it on the page, not in a chat bubble.",
    sub: "Drafts render right on the manuscript, in blue, exactly where they'd sit if kept.",
  },
  {
    n: "04",
    caption: "Keep it, rewrite it, or throw it away.",
    sub: "Regenerating costs nothing — only accepting touches your manuscript.",
  },
  {
    n: "05",
    caption: "Finish the chapter — it remembers the rest.",
    sub: "Every later chapter already knows what happened, automatically.",
  },
];

function LoopNode({ step }: { step: (typeof STEPS)[number] }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.6 });

  return (
    <div ref={ref} className="grid gap-3 md:grid-rows-subgrid md:row-span-3">
      <span
        className={cn(
          "font-mono text-2xl font-medium transition-colors duration-500",
          inView ? "text-primary" : "text-graphite",
        )}
      >
        {step.n}
      </span>
      <p className="font-display text-base font-medium leading-snug">{step.caption}</p>
      <p className="text-sm text-muted-foreground">{step.sub}</p>
    </div>
  );
}

export function TheLoop() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: sectionRef, offset: ["start 0.7", "end 0.3"] });
  const fillScaleX = useTransform(scrollYProgress, [0, 1], [0, 1]);

  return (
    <section id="loop" className={cn(styles.section, styles.tintB)}>
      <div ref={sectionRef} className="mx-auto max-w-[1200px] px-6">
        <motion.h2
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.4 }}
          transition={{ type: "spring", stiffness: 340, damping: 30 }}
          className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground"
        >
          The loop
        </motion.h2>

        <div className="mt-8 grid grid-cols-1 gap-10 md:grid-cols-5 md:grid-rows-[auto_auto_auto] md:gap-x-6 md:gap-y-4">
          {STEPS.map((step) => (
            <LoopNode key={step.n} step={step} />
          ))}
        </div>

        <LoopConnector fillScaleX={fillScaleX} />
      </div>
    </section>
  );
}
