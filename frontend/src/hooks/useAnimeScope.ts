import { createScope, type Scope } from "animejs";
import { useEffect, useRef } from "react";

export function useAnimeScope<T extends HTMLElement | SVGElement = HTMLDivElement>(
  setup: (scope?: Scope) => void,
  deps: unknown[] = [],
) {
  const root = useRef<T>(null);
  const scope = useRef<Scope | null>(null);

  useEffect(() => {
    if (!root.current) return;
    scope.current = createScope({ root: root.current }).add(setup);
    return () => scope.current?.revert();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  return root;
}
