import { useEffect } from "react";

type KeyMap = Record<string, (e: KeyboardEvent) => void>;

function comboFor(e: KeyboardEvent): string {
  const parts: string[] = [];
  if (e.metaKey || e.ctrlKey) parts.push("mod");
  if (e.shiftKey) parts.push("shift");
  const key = e.key.length === 1 ? e.key.toLowerCase() : e.key;
  if (key !== "Meta" && key !== "Control" && key !== "Shift") parts.push(key);
  return parts.join("+");
}

// Declarative key → handler map, e.g. { "mod+Enter": generate, "mod+k": accept }.
export function useKeyboardMap(map: KeyMap, active = true) {
  useEffect(() => {
    if (!active) return;
    function handler(e: KeyboardEvent) {
      const handler = map[comboFor(e)];
      if (handler) {
        e.preventDefault();
        handler(e);
      }
    }
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, map]);
}
