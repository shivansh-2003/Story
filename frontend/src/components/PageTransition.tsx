import type { ReactNode } from "react";
import { useLocation } from "react-router-dom";
import { motion, useReducedMotion } from "motion/react";
import { easeOut } from "@/lib/motion";

// Enter-only fade, no AnimatePresence/exit tracking. mode="wait" here
// previously forced every navigation to sit through the *outgoing* page's
// 420ms exit animation before the new route even started mounting — on top
// of its own lazy-chunk load and data fetch, a click could sit dead for the
// better part of a second, especially across very different route trees
// (e.g. the galley's bare shell <-> the app shell). Keying a bare div by
// pathname still gets a clean crossfade-in with none of that serialized
// wait, since React just swaps the subtree in the same commit.
export function PageTransition({ children }: { children: ReactNode }) {
  const location = useLocation();
  const reduced = useReducedMotion();

  return (
    <motion.div
      key={location.pathname}
      initial={{ opacity: 0, y: reduced ? 0 : 6 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduced ? 0 : 0.22, ease: easeOut }}
    >
      {children}
    </motion.div>
  );
}
