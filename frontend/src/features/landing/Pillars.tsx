import { useRef } from "react";
import { motion, useInView } from "motion/react";
import { cn } from "@/lib/utils";
import { PillarGlyph } from "./PillarGlyphs";
import styles from "./landing.module.css";

const CARDS = [
  {
    variant: "continuity" as const,
    title: "Continuity",
    body: "Your cast is structured data — not a paragraph you retype into every prompt by hand.",
  },
  {
    variant: "control" as const,
    title: "Control",
    body: "Nothing lands in your manuscript without your say-so. Every AI paragraph is a draft first.",
  },
  {
    variant: "iteration" as const,
    title: "Iteration",
    body: "Regenerating or discarding a draft never touches the database. Try five openings for the price of one.",
  },
];

const container = {
  hidden: {},
  show: { transition: { staggerChildren: 0.12 } },
};
const item = {
  hidden: { opacity: 0, y: 28 },
  show: { opacity: 1, y: 0, transition: { type: "spring" as const, stiffness: 340, damping: 30 } },
};

function PillarCard({ card }: { card: (typeof CARDS)[number] }) {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.4 });

  return (
    <motion.div
      ref={ref}
      variants={item}
      whileHover={{ y: -2 }}
      transition={{ duration: 0.2 }}
      className="rounded-lg border border-border bg-card p-6 transition-colors hover:border-primary/35"
    >
      <PillarGlyph variant={card.variant} trigger={inView} />
      <h3 className="mt-4 font-mono text-xs uppercase tracking-[0.14em] text-primary">{card.title}</h3>
      <p className="mt-3 text-sm text-muted-foreground">{card.body}</p>
    </motion.div>
  );
}

export function Pillars() {
  return (
    <section id="pillars" className={cn(styles.section, styles.tintA)}>
      <div className="mx-auto max-w-[1200px] px-6">
        <motion.div
          variants={container}
          initial="hidden"
          whileInView="show"
          viewport={{ once: true, amount: 0.3 }}
          className="grid grid-cols-1 gap-4 sm:grid-cols-3"
        >
          {CARDS.map((card) => (
            <PillarCard key={card.title} card={card} />
          ))}
        </motion.div>
      </div>
    </section>
  );
}
