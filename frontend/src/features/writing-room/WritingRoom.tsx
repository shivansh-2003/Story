import { useEffect, useState, type FormEvent, type KeyboardEvent } from "react";
import { Link, useParams } from "react-router-dom";
import { createAndActivateCharacter, getChapter, updateChapter } from "@/features/chapters/chaptersApi";
import type { ChapterDetail } from "@/lib/types";
import styles from "./WritingRoom.module.css";
import { useChapterSession } from "./useChapterSession";
import { useDebouncedManualEdit } from "./useDebouncedManualEdit";

type Length = "short" | "standard" | "long";

export function WritingRoom() {
  const { storyId = "", chapterId = "" } = useParams();
  const {
    state,
    loadChapter,
    doGenerate,
    doEditInstruction,
    doManualEdit,
    doAccept,
    doDiscard,
    restoreSibling,
    doComplete,
  } = useChapterSession(storyId, chapterId);

  const [chapterMeta, setChapterMeta] = useState<ChapterDetail | null>(null);
  const [instruction, setInstruction] = useState("");
  const [length, setLength] = useState<Length>("standard");
  const [justAccepted, setJustAccepted] = useState(false);
  const syncManualEdit = useDebouncedManualEdit(storyId, chapterId, doManualEdit);

  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");
  const [titleSaving, setTitleSaving] = useState(false);

  const [showAddCharacter, setShowAddCharacter] = useState(false);
  const [newCharName, setNewCharName] = useState("");
  const [newCharRole, setNewCharRole] = useState("");
  const [addCharacterBusy, setAddCharacterBusy] = useState(false);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    loadChapter();
    getChapter(storyId, chapterId).then(setChapterMeta);
  }, [loadChapter, storyId, chapterId]);

  const isBusy = state.status === "generating" || state.status === "accepting" || state.status === "completing";

  async function handleAccept() {
    await doAccept();
    setJustAccepted(true);
    setTimeout(() => setJustAccepted(false), 950);
  }

  function startEditingTitle() {
    setTitleDraft(chapterMeta?.title ?? "");
    setEditingTitle(true);
  }

  async function saveTitle() {
    const nextTitle = titleDraft.trim();
    setEditingTitle(false);
    if (!chapterMeta || nextTitle === (chapterMeta.title ?? "")) return;

    setTitleSaving(true);
    try {
      const updated = await updateChapter(storyId, chapterId, { title: nextTitle || null });
      setChapterMeta((meta) => (meta ? { ...meta, title: updated.title } : meta));
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setTitleSaving(false);
    }
  }

  function handleTitleKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter") e.currentTarget.blur(); // triggers saveTitle via onBlur
    if (e.key === "Escape") setEditingTitle(false);
  }

  async function handleAddCharacter(e: FormEvent) {
    e.preventDefault();
    setAddCharacterBusy(true);
    try {
      const character = await createAndActivateCharacter(storyId, chapterId, {
        name: newCharName,
        role: newCharRole || null,
      });
      // Nudge the model that this character is new to the moment, not just
      // present in a flat cast list — otherwise nothing in the prompt signals
      // they weren't already standing there.
      setInstruction((prev) =>
        prev.trim() ? `${prev.trim()} ${character.name} enters the scene.` : `${character.name} enters the scene.`,
      );
      setNotice(
        `${character.name} added to this chapter — appears starting with your next generation. The current draft isn't affected.`,
      );
      setTimeout(() => setNotice(null), 8000);
      setNewCharName("");
      setNewCharRole("");
      setShowAddCharacter(false);
    } catch (err) {
      setNotice((err as Error).message);
    } finally {
      setAddCharacterBusy(false);
    }
  }

  return (
    <div className={styles.room}>
      <div className={styles.topbar}>
        <Link className={styles.backLink} to={`/stories/${storyId}`}>
          ← story
        </Link>
        {editingTitle ? (
          <input
            className={styles.chapterTitleInput}
            value={titleDraft}
            onChange={(e) => setTitleDraft(e.target.value)}
            onBlur={saveTitle}
            onKeyDown={handleTitleKeyDown}
            placeholder="Untitled chapter"
            autoFocus
          />
        ) : (
          <h1
            className={styles.chapterTitle}
            onClick={startEditingTitle}
            title="Click to rename"
            aria-busy={titleSaving}
          >
            {chapterMeta?.title ?? "Untitled chapter"}
          </h1>
        )}
        <span className={styles.statusBadge}>{state.chapterStatus ?? chapterMeta?.status ?? "…"}</span>
      </div>

      <div className={styles.page}>
        <div className={styles.manuscript}>
          {state.acceptedParagraphs.length === 0 && !state.pendingTurn && (
            <p className={styles.empty}>The page is blank. Tell the assistant what happens first.</p>
          )}
          {state.acceptedParagraphs.map((p, i) => (
            <p
              key={i}
              className={justAccepted && i === state.acceptedParagraphs.length - 1 ? styles.settling : undefined}
            >
              {p}
            </p>
          ))}
        </div>

        {state.pendingTurn && (
          <div className={styles.draftBlock}>
            <textarea
              className={styles.draftTextarea}
              value={state.pendingTurn.content}
              onChange={(e) => syncManualEdit(e.target.value)}
              disabled={isBusy}
            />
            <div className={styles.draftMeta}>
              draft — {state.pendingTurn.source === "ai" ? "not yet accepted" : "hand-edited, not yet accepted"}
            </div>
            <div className={styles.toolbar}>
              <button
                className={styles.toolbarBtn}
                onClick={() => doEditInstruction(instruction)}
                disabled={isBusy || !instruction.trim()}
              >
                ✎ Edit with instruction
              </button>
              <button className={styles.toolbarBtn} onClick={() => doGenerate(instruction, length)} disabled={isBusy}>
                ↻ Regenerate
              </button>
              <button className={styles.toolbarBtnPrimary} onClick={handleAccept} disabled={isBusy}>
                ✓ Keep &amp; continue
              </button>
              <button className={styles.toolbarBtnDanger} onClick={doDiscard} disabled={isBusy}>
                ✕ Discard
              </button>
            </div>
          </div>
        )}

        {state.siblingAttempts.length > 0 && (
          <div className={styles.siblings}>
            {state.siblingAttempts.map((t, i) => (
              <button key={i} className={styles.siblingBtn} onClick={() => restoreSibling(t)}>
                previous draft {i + 1}
              </button>
            ))}
          </div>
        )}
      </div>

      <div className={styles.castRow}>
        <button className={styles.castToggle} onClick={() => setShowAddCharacter((v) => !v)}>
          {showAddCharacter ? "cancel" : "+ add a character to this scene"}
        </button>
      </div>

      {showAddCharacter && (
        <form className={styles.castForm} onSubmit={handleAddCharacter}>
          <div className={styles.castFormRow}>
            <input
              className={styles.castInput}
              value={newCharName}
              onChange={(e) => setNewCharName(e.target.value)}
              placeholder="Character name"
              autoFocus
              required
            />
            <input
              className={styles.castInput}
              value={newCharRole}
              onChange={(e) => setNewCharRole(e.target.value)}
              placeholder="Role (optional)"
            />
            <button className={styles.toolbarBtnPrimary} type="submit" disabled={addCharacterBusy || !newCharName.trim()}>
              Add
            </button>
          </div>
          <span className={styles.castHint}>
            Applies to your next generation, not the draft currently pending.
          </span>
        </form>
      )}

      {notice && <div className={styles.notice}>{notice}</div>}

      <div className={styles.compose}>
        <textarea
          className={styles.composeTextarea}
          value={instruction}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="Tell the assistant what happens next…"
          disabled={isBusy}
        />
        <div className={styles.composeFooter}>
          <div className={styles.lengthGroup}>
            {(["short", "standard", "long"] as const).map((l) => (
              <button
                key={l}
                className={l === length ? styles.lengthOptSelected : styles.lengthOpt}
                onClick={() => setLength(l)}
              >
                {l}
              </button>
            ))}
          </div>
          <button
            className={styles.generateBtn}
            onClick={() => doGenerate(instruction, length)}
            disabled={isBusy || !instruction.trim()}
          >
            Generate →
          </button>
        </div>
      </div>

      {state.errorMessage && <div className={styles.errorBanner}>{state.errorMessage}</div>}

      <div className={styles.completeRow}>
        <button className={styles.completeBtn} onClick={doComplete} disabled={isBusy || !!state.pendingTurn}>
          Mark chapter complete
        </button>
      </div>
    </div>
  );
}
