import { Link } from "react-router-dom";
import { motion, useInView } from "motion/react";
import { useRef } from "react";

export function LandingFooter() {
  const ref = useRef<HTMLDivElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.3 });

  return (
    <motion.footer
      ref={ref}
      initial={{ opacity: 0 }}
      animate={inView ? { opacity: 1 } : undefined}
      transition={{ duration: 0.5 }}
      className="border-t border-border bg-background"
    >
      <div className="mx-auto grid max-w-[1200px] grid-cols-1 gap-8 px-6 py-12 text-sm sm:grid-cols-3">
        <div>
          <p className="font-display text-base font-medium tracking-tight">
            story<span className="text-primary">assistant</span>
          </p>
          <p className="mt-2 max-w-xs text-muted-foreground">Co-written, one paragraph at a time.</p>
        </div>
        <div className="flex flex-col gap-2">
          <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">Product</span>
          <a href="#loop" className="text-muted-foreground hover:text-foreground">The loop</a>
          <a href="#bible" className="text-muted-foreground hover:text-foreground">The bible</a>
        </div>
        <div className="flex flex-col gap-2">
          <span className="font-mono text-xs uppercase tracking-wide text-muted-foreground">Account</span>
          <Link to="/login" className="text-muted-foreground hover:text-foreground">Sign in</Link>
          <Link to="/signup" className="text-muted-foreground hover:text-foreground">Create an account</Link>
        </div>
      </div>
      <div className="border-t border-border px-6 py-4 text-center text-xs text-muted-foreground">
        © storyassistant
      </div>
    </motion.footer>
  );
}
