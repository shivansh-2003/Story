import { motion, type MotionValue } from "motion/react";
import styles from "./landing.module.css";

// The scroll-scrubbed fill line beneath the loop's five nodes — isolated so
// the scroll-linked math (owned by TheLoop) stays decoupled from the node
// activation state (owned by each node's own useInView).
export function LoopConnector({ fillScaleX }: { fillScaleX: MotionValue<number> }) {
  return (
    <div className="relative mt-8 hidden h-px w-full md:block">
      <div className={`absolute inset-0 ${styles.connectorBase}`} />
      <motion.div className={`absolute inset-0 ${styles.connectorFill}`} style={{ scaleX: fillScaleX }} />
    </div>
  );
}
