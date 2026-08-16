import { useRef } from "react";
import { Link } from "react-router-dom";
import { motion, useInView } from "motion/react";
import { animate, utils } from "animejs";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { useAnimeScope } from "@/hooks/useAnimeScope";
import { prefersReducedMotion } from "@/lib/motion";
import styles from "./landing.module.css";

export function ClosingCTA() {
  const sectionRef = useRef<HTMLDivElement>(null);
  const inView = useInView(sectionRef, { once: true, amount: 0.4 });

  // Callback to the hero's FINAL sweep — same inkSettle mechanism, this
  // time on "call". A reader who scrolled the whole page recognizes the
  // gesture closing the loop the hero opened.
  const scope = useAnimeScope(() => {
    if (prefersReducedMotion()) {
      utils.set("[data-closing-sweep]", { "--sweep": "100%" });
      return;
    }
    if (!inView) return;
    animate("[data-closing-sweep]", {
      "--sweep": ["0%", "100%"],
      duration: 620,
      ease: "cubicBezier(.16,.84,.3,1)",
    });
  }, [inView]);

  return (
    <section className={cn(styles.section, styles.sectionEnd, "bg-card")}>
      <div ref={sectionRef} className="mx-auto max-w-[1200px] px-6 text-center">
        <h2 ref={scope} className="font-display text-3xl font-medium sm:text-4xl">
          Your words. Your{" "}
          <span data-closing-sweep className="ink-sweep">
            call
          </span>
          , every time.
        </h2>

        <motion.div
          initial="rest"
          whileHover="hover"
          animate="rest"
          className={cn("mt-8 inline-block", styles.ringButton)}
        >
          <Button size="lg" asChild>
            <Link to="/signup">Start writing →</Link>
          </Button>
          <svg className={styles.ringSvg} width="100%" height="100%">
            <motion.rect
              x="1"
              y="1"
              width="calc(100% - 2px)"
              height="calc(100% - 2px)"
              rx="10"
              fill="none"
              stroke="rgb(var(--nonrepro))"
              strokeWidth="1"
              variants={{ rest: { pathLength: 0, opacity: 0 }, hover: { pathLength: 1, opacity: 1 } }}
              transition={{ duration: 0.4, ease: "easeOut" }}
            />
          </svg>
        </motion.div>

        <p className="mt-4 text-sm text-muted-foreground">No credit card. Just an email.</p>
      </div>
    </section>
  );
}
