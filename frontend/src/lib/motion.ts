export const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

export const easeOut = [0.22, 1, 0.36, 1] as const;
export const easeSettle = [0.16, 0.84, 0.3, 1] as const;
