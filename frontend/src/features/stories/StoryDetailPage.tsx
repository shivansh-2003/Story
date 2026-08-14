import { useEffect, useState, type FormEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { createChapter, listChapters } from "@/features/chapters/chaptersApi";
import { listCharacters } from "@/features/characters/charactersApi";
import type { Chapter, Character, POV, StoryDetail, Tense } from "@/lib/types";
import styles from "@/styles/shared.module.css";
import { getStory, importCharacterToStory, updateStory, type StoryInput } from "./storiesApi";
import local from "./StoryDetailPage.module.css";

const emptyBibleForm: StoryInput = {
  title: "",
  genre: [],
  tone: "",
  pov: null,
  tense: null,
  rating: "",
  premise: "",
  opening_line: "",
  setting: "",
  themes: [],
  content_boundaries: "",
  writing_style_notes: "",
  target_audience: "",
};

function bibleFormFrom(story: StoryDetail): StoryInput {
  return {
    title: story.title,
    genre: story.genre ?? [],
    tone: story.tone ?? "",
    pov: story.pov,
    tense: story.tense,
    rating: story.rating ?? "",
    premise: story.premise ?? "",
    opening_line: story.opening_line ?? "",
    setting: story.setting ?? "",
    themes: story.themes ?? [],
    content_boundaries: story.content_boundaries ?? "",
    writing_style_notes: story.writing_style_notes ?? "",
    target_audience: story.target_audience ?? "",
  };
}

export function StoryDetailPage() {
  const { storyId = "" } = useParams();
  const [story, setStory] = useState<StoryDetail | null>(null);
  const [chapters, setChapters] = useState<Chapter[] | null>(null);
  const [allCharacters, setAllCharacters] = useState<Character[]>([]);
  const [pickedCharacter, setPickedCharacter] = useState("");
  const [newChapterTitle, setNewChapterTitle] = useState("");
  const [error, setError] = useState<string | null>(null);

  const [editingBible, setEditingBible] = useState(false);
  const [bibleForm, setBibleForm] = useState<StoryInput>(emptyBibleForm);
  const [bibleSaving, setBibleSaving] = useState(false);

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

  function startEditingBible() {
    if (story) setBibleForm(bibleFormFrom(story));
    setEditingBible(true);
  }

  async function handleSaveBible(e: FormEvent) {
    e.preventDefault();
    setBibleSaving(true);
    try {
      const updated = await updateStory(storyId, {
        ...bibleForm,
        genre: bibleForm.genre?.length ? bibleForm.genre : null,
        themes: bibleForm.themes?.length ? bibleForm.themes : null,
      });
      setStory((s) => (s ? { ...s, ...updated } : s));
      setEditingBible(false);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBibleSaving(false);
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

        {!editingBible && (
          <>
            <button className={local.editToggle} onClick={startEditingBible}>
              edit story bible
            </button>
            <div className={local.bible}>
              {story.genre?.map((g) => (
                <span key={g} className={local.bibleTag}>
                  {g}
                </span>
              ))}
              {story.tone && <span className={local.bibleTag}>{story.tone}</span>}
              {story.pov && <span className={local.bibleTag}>{story.pov.replace("_", " ")}</span>}
              {story.tense && <span className={local.bibleTag}>{story.tense} tense</span>}
              {story.target_audience && <span className={local.bibleTag}>{story.target_audience}</span>}
            </div>
            {story.themes && story.themes.length > 0 && (
              <div className={local.bible}>
                {story.themes.map((t) => (
                  <span key={t} className={local.bibleTag}>
                    {t}
                  </span>
                ))}
              </div>
            )}
            {story.premise && <p className={local.premise}>{story.premise}</p>}
            {story.setting && <p className={local.premise}>{story.setting}</p>}
            {story.writing_style_notes && (
              <p className={styles.cardMeta}>Style: {story.writing_style_notes}</p>
            )}
            {story.content_boundaries && (
              <p className={styles.cardMeta}>Boundaries: {story.content_boundaries}</p>
            )}
          </>
        )}

        {editingBible && (
          <form className={local.bibleForm} onSubmit={handleSaveBible}>
            <span className={styles.formTitle}>Edit story bible</span>
            <div className={local.bibleFormGrid}>
              <label className={styles.label}>
                Title
                <input
                  className={styles.input}
                  value={bibleForm.title}
                  onChange={(e) => setBibleForm((f) => ({ ...f, title: e.target.value }))}
                  required
                />
              </label>
              <label className={styles.label}>
                Genre (comma separated)
                <input
                  className={styles.input}
                  value={bibleForm.genre?.join(", ") ?? ""}
                  onChange={(e) =>
                    setBibleForm((f) => ({
                      ...f,
                      genre: e.target.value.split(",").map((v) => v.trim()).filter(Boolean),
                    }))
                  }
                />
              </label>
              <label className={styles.label}>
                Tone
                <input
                  className={styles.input}
                  value={bibleForm.tone ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, tone: e.target.value }))}
                />
              </label>
              <label className={styles.label}>
                Rating
                <input
                  className={styles.input}
                  value={bibleForm.rating ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, rating: e.target.value }))}
                />
              </label>
              <label className={styles.label}>
                POV
                <select
                  className={styles.select}
                  value={bibleForm.pov ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, pov: (e.target.value || null) as POV | null }))}
                >
                  <option value="">Unset</option>
                  <option value="first_person">First person</option>
                  <option value="third_limited">Third limited</option>
                  <option value="third_omniscient">Third omniscient</option>
                </select>
              </label>
              <label className={styles.label}>
                Tense
                <select
                  className={styles.select}
                  value={bibleForm.tense ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, tense: (e.target.value || null) as Tense | null }))}
                >
                  <option value="">Unset</option>
                  <option value="past">Past</option>
                  <option value="present">Present</option>
                </select>
              </label>
              <label className={styles.label}>
                Target audience
                <input
                  className={styles.input}
                  value={bibleForm.target_audience ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, target_audience: e.target.value }))}
                />
              </label>
              <label className={styles.label}>
                Themes (comma separated)
                <input
                  className={styles.input}
                  value={bibleForm.themes?.join(", ") ?? ""}
                  onChange={(e) =>
                    setBibleForm((f) => ({
                      ...f,
                      themes: e.target.value.split(",").map((v) => v.trim()).filter(Boolean),
                    }))
                  }
                />
              </label>
              <label className={`${styles.label} ${local.bibleFormWide}`}>
                Premise
                <textarea
                  className={styles.textarea}
                  value={bibleForm.premise ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, premise: e.target.value }))}
                />
              </label>
              <label className={`${styles.label} ${local.bibleFormWide}`}>
                Setting (time period, world)
                <textarea
                  className={styles.textarea}
                  value={bibleForm.setting ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, setting: e.target.value }))}
                />
              </label>
              <label className={`${styles.label} ${local.bibleFormWide}`}>
                Opening line
                <input
                  className={styles.input}
                  value={bibleForm.opening_line ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, opening_line: e.target.value }))}
                />
              </label>
              <label className={`${styles.label} ${local.bibleFormWide}`}>
                Writing style notes (sentence rhythm, dialogue density…)
                <textarea
                  className={styles.textarea}
                  value={bibleForm.writing_style_notes ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, writing_style_notes: e.target.value }))}
                />
              </label>
              <label className={`${styles.label} ${local.bibleFormWide}`}>
                Content boundaries (explicit dos/don'ts)
                <textarea
                  className={styles.textarea}
                  value={bibleForm.content_boundaries ?? ""}
                  onChange={(e) => setBibleForm((f) => ({ ...f, content_boundaries: e.target.value }))}
                />
              </label>
            </div>
            <div className={local.pickerRow}>
              <button className={styles.primaryBtn} type="submit" disabled={bibleSaving}>
                {bibleSaving ? "Saving…" : "Save"}
              </button>
              <button className={styles.secondaryBtn} type="button" onClick={() => setEditingBible(false)}>
                Cancel
              </button>
            </div>
          </form>
        )}
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
