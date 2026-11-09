"use client";

import { useEffect, useRef, useState } from "react";
import { useFormStatus } from "react-dom";

const PAUSE_MS = 1000;   // a pause in typing this long saves the note

/**
 * A rating's note on /fit, saved as it is written (David, 9 Nov 2026): a pause in typing, or leaving the box, submits
 * the row's form, which carries the slider's rating with it. A note needs a rating, so the box waits until the row is
 * rated. The box is controlled so that React's reset of the form after a save cannot drop what was typed meanwhile.
 */
export function FitNote({ id, name, note, rated }: { id: string; name: string; note: string; rated: boolean }) {
  const box = useRef<HTMLTextAreaElement>(null);
  const [text, setText] = useState(note);
  const saved = useRef(note);
  const timer = useRef<number | undefined>(undefined);
  const { pending } = useFormStatus();
  const [state, setState] = useState<"" | "waiting" | "saved">("");
  const wasPending = useRef(false);

  useEffect(() => {   // the page sends the stored note back after a save or a Clear; take it unless more was typed since
    const now = box.current?.value ?? "";
    const typedSince = now.trim() !== saved.current.trim();
    saved.current = note;
    if (!typedSince && now.trim() !== note) setText(note);
  }, [note]);

  useEffect(() => {   // say Saved once a save this box started has gone through
    if (state === "waiting" && wasPending.current && !pending) setState("saved");
    wasPending.current = pending;
  }, [pending, state]);

  useEffect(() => {
    if (state !== "saved") return undefined;
    const done = window.setTimeout(() => setState(""), 2000);
    return () => window.clearTimeout(done);
  }, [state]);

  useEffect(() => {   // the box grows with the note, so nothing is hidden behind a scroll bar
    const el = box.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight + el.offsetHeight - el.clientHeight}px`;
  }, [text]);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  const save = () => {
    window.clearTimeout(timer.current);
    const el = box.current;
    if (!el || !rated || el.value.trim() === saved.current.trim()) return;
    saved.current = el.value;
    setState("waiting");
    el.form?.requestSubmit();
  };

  return (
    <div className="fit-note">
      <label className="sr-only" htmlFor={id}>Note on {name}</label>
      <textarea
        ref={box}
        id={id}
        name="note"
        value={text}
        maxLength={500}
        rows={Math.max(1, Math.ceil(note.length / 48))}
        disabled={!rated}
        placeholder={rated ? "Note: why, or when it changes. It saves as you type." : "Rate it first to add a note"}
        onChange={(event) => {
          setText(event.target.value);
          window.clearTimeout(timer.current);
          timer.current = window.setTimeout(save, PAUSE_MS);
        }}
        onBlur={save}
      />
      <span className="fit-note-state" aria-live="polite">{state === "saved" ? "Note saved" : ""}</span>
    </div>
  );
}
