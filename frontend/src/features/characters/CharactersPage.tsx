import { useEffect, useState, type FormEvent } from "react";
import type { Character } from "@/lib/types";
import styles from "@/styles/shared.module.css";
import { createCharacter, listCharacters } from "./charactersApi";

const emptyForm = { name: "", role: "", motivation: "", backstory: "" };

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
        motivation: form.motivation || null,
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

      <form className={styles.form} onSubmit={handleCreate}>
        <span className={styles.formTitle}>New character</span>
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
          Motivation
          <textarea
            className={styles.textarea}
            value={form.motivation}
            onChange={(e) => setForm((f) => ({ ...f, motivation: e.target.value }))}
          />
        </label>
        <label className={styles.label}>
          Backstory
          <textarea
            className={styles.textarea}
            value={form.backstory}
            onChange={(e) => setForm((f) => ({ ...f, backstory: e.target.value }))}
          />
        </label>
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
