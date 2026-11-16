"use client";

import { useEffect, useRef, useState } from "react";
import { saveNoteAction } from "@/app/actions";

const PAUSE_MS = 1000;   // a pause in typing this long saves the note

type State = { kind: "" | "saving" | "saved" | "error"; text: string };

const clean = (text: string) => text.replace(/\s+/g, " ").trim();

/**
 * A call's note box under Add a note (David, 16 Nov 2026): what is typed saves itself under the person signed in, a
 * second after the typing stops or on leaving the box, with no decision needed and the call's decision left alone.
 * Later saves from the box edit that same note, and emptying the box takes it away. Saves run one after another, each
 * sending the stamp the last one returned, so a quick second save cannot add a second note. The box keeps its name,
 * `note`, inside the Decide form: a decision chosen while it holds text carries the note too (after a Not relevant
 * reason), and the decision's line takes the place of the one saved here. A reset of the form starts a new note.
 */
export function CallNote({ callId, title }: { callId: string; title: string }) {
  const box = useRef<HTMLTextAreaElement>(null);
  const at = useRef<string | null>(null);   // the stamp of the line this box wrote, while it has one
  const saved = useRef("");                 // what that line says
  const chain = useRef<Promise<void>>(Promise.resolve());
  const timer = useRef<number | undefined>(undefined);
  const [state, setState] = useState<State>({ kind: "", text: "" });

  useEffect(() => {
    const form = box.current?.form;
    const restart = () => {
      window.clearTimeout(timer.current);
      at.current = null;
      saved.current = "";
    };
    form?.addEventListener("reset", restart);
    return () => {
      form?.removeEventListener("reset", restart);
      window.clearTimeout(timer.current);
    };
  }, []);

  useEffect(() => {
    if (state.kind !== "saved") return undefined;
    const done = window.setTimeout(() => setState({ kind: "", text: "" }), 2500);
    return () => window.clearTimeout(done);
  }, [state]);

  const save = () => {
    window.clearTimeout(timer.current);
    chain.current = chain.current.then(async () => {
      const text = box.current?.value ?? "";
      if (clean(text) === clean(saved.current)) return;
      setState({ kind: "saving", text: "Saving..." });
      let result: Awaited<ReturnType<typeof saveNoteAction>>;
      try {
        result = await saveNoteAction({ callId, at: at.current, text });
      } catch {
        result = { ok: false, reason: "Could not reach the dashboard. The note is not saved yet." };
      }
      if (!result.ok) {
        setState({ kind: "error", text: result.reason });   // the next change or leaving the box tries again
        return;
      }
      at.current = result.at;
      saved.current = result.at ? text : "";
      setState({ kind: "saved", text: result.at ? "Note saved" : "Note removed" });
    });
  };

  return (
    <>
      <textarea
        ref={box}
        name="note"
        maxLength={2000}
        rows={3}
        placeholder="Saves as you type, under your name"
        aria-label={`Note on ${title}`}
        onChange={() => {
          window.clearTimeout(timer.current);
          timer.current = window.setTimeout(save, PAUSE_MS);
        }}
        onBlur={save}
      />
      <span className={`call-note-state ${state.kind}`} role="status">
        {state.text}
      </span>
    </>
  );
}
