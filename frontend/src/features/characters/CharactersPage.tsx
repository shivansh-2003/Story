import { useEffect, useState, type FormEvent } from "react";
import type { Character } from "@/lib/types";
import styles from "@/styles/shared.module.css";
import { createCharacter, listCharacters } from "./charactersApi";
import local from "./CharactersPage.module.css";

const emptyForm = {
  name: "",
  role: "",
  age: "",
  pronouns: "",
  appearance: "",
  voice_notes: "",
  personality_traits: "",
  motivation: "",
  flaw: "",
  backstory: "",
};

export function CharactersPage() {
  const [characters, setCharacters] = useState<Character[] | null>(null);
  const [form, setForm] = useState(emptyForm);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    listCharacters().then(setCharacters);
  }, []);

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const character = await createCharacter({
        name: form.name,
        role: form.role || null,
        age: form.age || null,
        pronouns: form.pronouns || null,
        appearance: form.appearance || null,
        voice_notes: form.voice_notes || null,
        personality_traits: form.personality_traits
          ? form.personality_traits.split(",").map((v) => v.trim()).filter(Boolean)
          : null,
        motivation: form.motivation || null,
        flaw: form.flaw || null,
        backstory: form.backstory || null,
      });
      setCharacters((c) => [...(c ?? []), character]);
      setForm(emptyForm);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className={styles.container}>
      <h1 className={styles.heading}>Your characters</h1>

      <form className={local.form} onSubmit={handleCreate}>
        <span className={styles.formTitle}>New character</span>
        <div className={local.grid}>
          <label className={styles.label}>
            Name
            <input
              className={styles.input}
              value={form.name}
              onChange={(e) => setForm((f) => ({ ...f, name: e.target.value }))}
              required
            />
          </label>
          <label className={styles.label}>
            Role
            <input
              className={styles.input}
              value={form.role}
              onChange={(e) => setForm((f) => ({ ...f, role: e.target.value }))}
              placeholder="protagonist, rival, mentor…"
            />
          </label>
          <label className={styles.label}>
            Age
            <input
              className={styles.input}
              value={form.age}
              onChange={(e) => setForm((f) => ({ ...f, age: e.target.value }))}
            />
          </label>
          <label className={styles.label}>
            Pronouns
            <input
              className={styles.input}
              value={form.pronouns}
              onChange={(e) => setForm((f) => ({ ...f, pronouns: e.target.value }))}
            />
          </label>
          <label className={`${styles.label} ${local.wide}`}>
            Appearance
            <textarea
              className={styles.textarea}
              value={form.appearance}
              onChange={(e) => setForm((f) => ({ ...f, appearance: e.target.value }))}
            />
          </label>
          <label className={`${styles.label} ${local.wide}`}>
            Voice notes (how they talk)
            <textarea
              className={styles.textarea}
              value={form.voice_notes}
              onChange={(e) => setForm((f) => ({ ...f, voice_notes: e.target.value }))}
            />
          </label>
          <label className={`${styles.label} ${local.wide}`}>
            Personality traits (comma separated)
            <input
              className={styles.input}
              value={form.personality_traits}
              onChange={(e) => setForm((f) => ({ ...f, personality_traits: e.target.value }))}
              placeholder="stubborn, dry humor, fiercely loyal"
            />
          </label>
          <label className={styles.label}>
            Motivation
            <textarea
              className={styles.textarea}
              value={form.motivation}
              onChange={(e) => setForm((f) => ({ ...f, motivation: e.target.value }))}
            />
          </label>
          <label className={styles.label}>
            Flaw
            <textarea
              className={styles.textarea}
              value={form.flaw}
              onChange={(e) => setForm((f) => ({ ...f, flaw: e.target.value }))}
            />
          </label>
          <label className={`${styles.label} ${local.wide}`}>
            Backstory
            <textarea
              className={styles.textarea}
              value={form.backstory}
              onChange={(e) => setForm((f) => ({ ...f, backstory: e.target.value }))}
            />
          </label>
        </div>
        {error && <span className={styles.errorText}>{error}</span>}
        <button className={styles.primaryBtn} type="submit" disabled={busy || !form.name.trim()}>
          {busy ? "Creating…" : "Create character"}
        </button>
      </form>

      {characters === null && <p className={styles.emptyState}>Loading…</p>}
      {characters?.length === 0 && <p className={styles.emptyState}>No characters yet — create one above.</p>}

      <div className={styles.grid}>
        {characters?.map((c) => (
          <div key={c.id} className={styles.card}>
            <div className={styles.cardTitle}>{c.name}</div>
            <div className={styles.cardMeta}>{c.role ?? "no role set"}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
