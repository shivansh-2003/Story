import { useLayoutEffect, useRef } from "react";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import type { ComponentProps } from "react";

export function AutosizeTextarea({ className, value, ...props }: ComponentProps<typeof Textarea>) {
  const ref = useRef<HTMLTextAreaElement>(null);

  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, [value]);

  return <Textarea ref={ref} value={value} className={cn("resize-none overflow-hidden", className)} {...props} />;
}
