import { useState, type KeyboardEvent } from "react";
import { Input } from "@/components/ui/input";

export function AddChapterRow({ onAdd }: { onAdd: (title: string) => void }) {
  const [title, setTitle] = useState("");

  function handleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") {
      onAdd(title.trim());
      setTitle("");
    }
  }

  return (
    <Input
      value={title}
      onChange={(e) => setTitle(e.target.value)}
      onKeyDown={handleKeyDown}
      placeholder="+ Add a chapter"
      className="mt-1 border-dashed text-sm text-muted-foreground focus:text-foreground"
    />
  );
}
