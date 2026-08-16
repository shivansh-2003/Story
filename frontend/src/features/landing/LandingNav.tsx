import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { motion, useMotionTemplate, useScroll, useTransform } from "motion/react";
import { Button } from "@/components/ui/button";

const SECTIONS = [
  { id: "loop", label: "The loop" },
  { id: "bible", label: "The bible" },
];

export function LandingNav() {
  const { scrollY } = useScroll();
  const blur = useTransform(scrollY, [0, 40], [0, 12]);
  const bgAlpha = useTransform(scrollY, [0, 40], [0, 0.72]);
  const borderAlpha = useTransform(scrollY, [0, 40], [0, 1]);
  const backdropFilter = useMotionTemplate`blur(${blur}px)`;
  const background = useMotionTemplate`rgb(var(--stock) / ${bgAlpha})`;
  const borderColor = useMotionTemplate`rgb(var(--border) / ${borderAlpha})`;

  const [active, setActive] = useState<string | null>(null);

  useEffect(() => {
    const targets = SECTIONS.map((s) => document.getElementById(s.id)).filter((el): el is HTMLElement => !!el);
    if (targets.length === 0) return;
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) setActive(entry.target.id);
        }
      },
      { rootMargin: "-45% 0px -45% 0px" },
    );
    targets.forEach((el) => observer.observe(el));
    return () => observer.disconnect();
  }, []);

  return (
    <motion.header
      style={{ backdropFilter, background, borderColor }}
      className="fixed inset-x-0 top-0 z-50 h-16 border-b"
    >
      <div className="mx-auto flex h-full max-w-[1200px] items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2 font-display text-lg font-medium tracking-tight">
          <motion.svg
            whileHover={{ scale: 1.08 }}
            transition={{ duration: 0.16 }}
            width="18"
            height="18"
            viewBox="0 0 18 18"
            fill="none"
          >
            <circle cx="9" cy="9" r="7" stroke="rgb(var(--nonrepro))" strokeWidth="1.5" />
          </motion.svg>
          story<span className="text-primary">assistant</span>
        </Link>

        <nav className="hidden items-center gap-6 md:flex">
          {SECTIONS.map((s) => (
            <a
              key={s.id}
              href={`#${s.id}`}
              className="relative py-2 text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {s.label}
              {active === s.id && (
                <motion.span
                  layoutId="nav-underline"
                  className="absolute inset-x-0 -bottom-px h-0.5 rounded-full bg-primary"
                  transition={{ type: "spring", stiffness: 500, damping: 40 }}
                />
              )}
            </a>
          ))}
        </nav>

        <Button variant="ghost" size="sm" asChild>
          <Link to="/login">Sign in</Link>
        </Button>
      </div>
    </motion.header>
  );
}
