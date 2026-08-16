import { useEffect, useRef, useState } from "react";
import { motion, useInView, useScroll } from "motion/react";
import { cn } from "@/lib/utils";
import styles from "./landing.module.css";

const FIELDS = [
  { label: "Tone", value: "bleak, tender" },
  { label: "POV", value: "third limited" },
  { label: "Tense", value: "past" },
  { label: "Themes", value: "duty, salt, inheritance" },
  { label: "Boundaries", value: "no on-page violence" },
];

// Each phrase index lines up with FIELDS[index] — the field lighting up on
// the left and the phrase underlining on the right are driven by the same
// bucket index, proving a specific field shapes specific words.
const PROSE: { text: string; phrase: number | null }[] = [
  { text: "The lamp ", phrase: null },
  { text: "had been dark for nine days", phrase: 0 },
  { text: " when Maren finally climbed the stair. ", phrase: null },
  { text: "She counted the steps", phrase: 1 },
  { text: " the way ", phrase: null },
  { text: "her father had taught her", phrase: 2 },
  { text: ", ", phrase: null },
  { text: "the way the house had always done things", phrase: 3 },
  { text: ", under her breath, out of habit more than fear.", phrase: null },
];

export function StoryBibleDemo() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const inView = useInView(sectionRef, { once: true, amount: 0.2 });
  const { scrollYProgress } = useScroll({ target: sectionRef, offset: ["start 0.75", "end 0.25"] });
  const [bucket, setBucket] = useState(0);

  useEffect(() => {
    return scrollYProgress.on("change", (v) => {
      const next = Math.min(4, Math.max(0, Math.floor(v * 5)));
      setBucket((prev) => (prev === next ? prev : next));
    });
  }, [scrollYProgress]);

  return (
    <section id="bible" className={cn(styles.section, styles.tintB)}>
      <div ref={sectionRef} className="mx-auto max-w-[1200px] px-6">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={inView ? { opacity: 1, y: 0 } : undefined}
          transition={{ type: "spring", stiffness: 340, damping: 30 }}
        >
          <h2 className="font-mono text-xs uppercase tracking-[0.14em] text-muted-foreground">The story bible</h2>
          <p className="mt-2 max-w-lg text-lg text-foreground">
            Set it once. Every generation call respects it — automatically.
          </p>
        </motion.div>

        <div className="mt-10 mb-10 grid grid-cols-1 items-start gap-8 md:mb-14 md:grid-cols-2 md:gap-12">
          <dl className="flex flex-col divide-y divide-border rounded-lg border border-border">
            {FIELDS.map((field, i) => (
              <div
                key={field.label}
                className={cn(
                  "flex items-baseline justify-between gap-4 px-4 py-3 transition-colors duration-300",
                  bucket === i && "bg-primary/10",
                )}
              >
                <dt
                  className={cn(
                    "font-mono text-xs uppercase tracking-wide transition-colors duration-300",
                    bucket === i ? "text-primary" : "text-muted-foreground",
                  )}
                >
                  {field.label}
                </dt>
                <dd className="text-right text-sm">{field.value}</dd>
              </div>
            ))}
          </dl>

          <div className="rounded-lg bg-sheet p-6 shadow-[var(--shadow-sheet)]">
            <p className="font-manuscript text-[1.0625rem] leading-relaxed" style={{ color: "rgb(var(--sheet-foreground))" }}>
              "
              {PROSE.map((part, i) => (
                <span
                  key={i}
                  className="transition-[text-decoration-color] duration-300"
                  style={{
                    textDecorationLine: part.phrase !== null ? "underline" : undefined,
                    textDecorationColor: part.phrase === bucket ? "rgb(var(--nonrepro))" : "transparent",
                    textDecorationThickness: "2px",
                    textUnderlineOffset: "3px",
                  }}
                >
                  {part.text}
                </span>
              ))}
              "
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}
