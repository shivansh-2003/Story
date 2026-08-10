import { useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import type { Story } from "@/lib/types";
import styles from "@/styles/shared.module.css";
import { createStory, listStories } from "./storiesApi";

export function StoriesListPage() {
  const [stories, setStories] = useState<Story[] | null>(null);
  const [title, setTitle] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listStories().then(setStories);
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const story = await createStory({ title });
      setStories((s) => [...(s ?? []), story]);
      setTitle("");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.container}>
      <h1 className={styles.heading}>Your stories</h1>

      <form className={styles.form} onSubmit={handleCreate}>
        <span className={styles.formTitle}>Start a new story</span>
        <label className={styles.label}>
          Title
          <input
            className={styles.input}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            placeholder="The Last Lighthouse Keeper"
            required
          />
        </label>
        {error && <span className={styles.errorText}>{error}</span>}
        <button className={styles.primaryBtn} type="submit" disabled={busy || !title.trim()}>
          {busy ? "Creating…" : "Create story"}
        </button>
      </form>

      {stories === null && <p className={styles.emptyState}>Loading…</p>}
      {stories?.length === 0 && <p className={styles.emptyState}>No stories yet — start one above.</p>}

      <div className={styles.grid}>
        {stories?.map((story) => (
          <Link key={story.id} className={styles.card} to={`/stories/${story.id}`}>
            <div className={styles.cardTitle}>{story.title}</div>
            <div className={styles.cardMeta}>
              {story.status} {story.genre?.length ? `· ${story.genre.join(", ")}` : ""}
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
