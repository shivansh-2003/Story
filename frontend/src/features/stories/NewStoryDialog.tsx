import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { createStory } from "./storiesApi";
import type { Story } from "@/lib/types";

export function NewStoryDialog() {
  const [open, setOpen] = useState(false);
  const [title, setTitle] = useState("");
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const mutation = useMutation({
    mutationFn: () => createStory({ title }),
    onSuccess: (story: Story) => {
      queryClient.setQueryData<Story[]>(["stories"], (prev) => [...(prev ?? []), story]);
      setOpen(false);
      setTitle("");
      navigate(`/stories/${story.id}/chapters`);
    },
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>+ New story</Button>
      </DialogTrigger>
      <DialogContent>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            mutation.mutate();
          }}
        >
          <DialogHeader>
            <DialogTitle>Name your story</DialogTitle>
            <DialogDescription>You can fill in the bible later.</DialogDescription>
          </DialogHeader>
          <div className="mt-4">
            <Label htmlFor="story-title">Title</Label>
            <Input
              id="story-title"
              className="mt-1.5"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="The Last Lighthouse Keeper"
              autoFocus
              required
            />
          </div>
          {mutation.isError && (
            <p role="alert" className="mt-3 font-mono text-xs uppercase tracking-wide text-destructive">
              {(mutation.error as Error).message}
            </p>
          )}
          <DialogFooter className="mt-6">
            <Button type="submit" disabled={!title.trim() || mutation.isPending}>
              {mutation.isPending ? "Creating…" : "Create story"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
