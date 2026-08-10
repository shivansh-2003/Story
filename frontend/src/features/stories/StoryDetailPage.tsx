import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { createChapter, listChapters } from "@/features/chapters/chaptersApi";
import { listCharacters } from "@/features/characters/charactersApi";
import type { Chapter, Character, StoryDetail } from "@/lib/types";
import styles from "@/styles/shared.module.css";
import { getStory, importCharacterToStory } from "./storiesApi";
import local from "./StoryDetailPage.module.css";

export function StoryDetailPage() {
  const { storyId = "" } = useParams();
  const [story, setStory] = useState<StoryDetail | null>(null);
  const [chapters, setChapters] = useState<Chapter[] | null>(null);
  const [allCharacters, setAllCharacters] = useState<Character[]>([]);
  const [pickedCharacter, setPickedCharacter] = useState("");
  const [newChapterTitle, setNewChapterTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function refresh() {
    const [storyDetail, chapterList, characters] = await Promise.all([
      getStory(storyId),
      listChapters(storyId),
      listCharacters(),
    ]);
    setStory(storyDetail);
    setChapters(chapterList);
    setAllCharacters(characters);
  }

  useEffect(() => {
    refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [storyId]);

  async function handleImport(e: FormEvent) {
    e.preventDefault();
    if (!pickedCharacter) return;
    try {
      await importCharacterToStory(storyId, pickedCharacter);
      setPickedCharacter("");
      await refresh();
    } catch (err) {
      setError((err as Error).message);
    }
  }

  async function handleCreateChapter(e: FormEvent) {
    e.preventDefault();
    try {
      const chapter = await createChapter(storyId, { title: newChapterTitle || null });
      setChapters((c) => [...(c ?? []), chapter]);
      setNewChapterTitle("");
    } catch (err) {
      setError((err as Error).message);
    }
  }

  if (!story) return <div className={styles.container}>Loading…</div>;

  const importedIds = new Set(story.characters.map((c) => c.id));
  const importable = allCharacters.filter((c) => !importedIds.has(c.id));

  return (
    <div className={styles.container}>
      <h1 className={styles.heading}>{story.title}</h1>

      <div className={local.section}>
        <div className={local.sectionTitle}>Story bible</div>
        <div className={local.bible}>
          {story.genre?.map((g) => (
            <span key={g} className={local.bibleTag}>
              {g}
            </span>
          ))}
          {story.tone && <span className={local.bibleTag}>{story.tone}</span>}
          {story.pov && <span className={local.bibleTag}>{story.pov.replace("_", " ")}</span>}
          {story.tense && <span className={local.bibleTag}>{story.tense} tense</span>}
        </div>
        {story.premise && <p className={local.premise}>{story.premise}</p>}
      </div>

      <div className={local.section}>
        <div className={local.sectionTitle}>Characters in this story</div>
        {story.characters.length === 0 && <p className={styles.emptyState}>None imported yet.</p>}
        <div className={styles.grid}>
          {story.characters.map((c) => (
            <div key={c.id} className={styles.card}>
              <div className={styles.cardTitle}>{c.name}</div>
              <div className={styles.cardMeta}>{c.role ?? "no role set"}</div>
            </div>
          ))}
        </div>
        {importable.length > 0 && (
          <form className={local.pickerRow} onSubmit={handleImport}>
            <select
              className={styles.select}
              value={pickedCharacter}
              onChange={(e) => setPickedCharacter(e.target.value)}
            >
              <option value="">Import a character…</option>
              {importable.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
            <button className={styles.secondaryBtn} type="submit" disabled={!pickedCharacter}>
              Import
            </button>
          </form>
        )}
      </div>

      <div className={local.section}>
        <div className={local.sectionTitle}>Chapters</div>
        {chapters?.length === 0 && <p className={styles.emptyState}>No chapters yet — start one below.</p>}
        {chapters
          ?.slice()
          .sort((a, b) => a.order_index - b.order_index)
          .map((chapter) => (
            <Link key={chapter.id} className={local.chapterRow} to={`/stories/${storyId}/chapters/${chapter.id}`}>
              <span className={local.chapterOrder}>{String(chapter.order_index + 1).padStart(2, "0")}</span>
              <span className={local.chapterTitle}>{chapter.title ?? "Untitled chapter"}</span>
              <span className={styles.cardMeta}>{chapter.status}</span>
            </Link>
          ))}

        <form className={local.pickerRow} style={{ marginTop: "var(--space-3)" }} onSubmit={handleCreateChapter}>
          <input
            className={styles.input}
            value={newChapterTitle}
            onChange={(e) => setNewChapterTitle(e.target.value)}
            placeholder="New chapter title (optional)"
          />
          <button className={styles.secondaryBtn} type="submit">
            Add chapter
          </button>
        </form>
      </div>

      {error && <p className={styles.errorText}>{error}</p>}
    </div>
  );
}
