"use client";

import { useEffect, useRef, useState, useTransition, type FormEvent, type ReactNode } from "react";
import { autoSaveProfileAction } from "@/app/actions";

const PAUSE_MS = 800;   // a pause in typing this long saves

type Field = HTMLInputElement | HTMLSelectElement | HTMLTextAreaElement;

/** A named field that takes part in the save; a file box (the picture) saves on its own. */
function fieldOf(target: EventTarget | null): Field | null {
  if (!(target instanceof HTMLInputElement || target instanceof HTMLSelectElement || target instanceof HTMLTextAreaElement)) return null;
  return target.name && target.type !== "file" ? target : null;
}

/** Typed into: these save after a pause or on leaving them; a choice saves at once. */
function typed(field: Field): boolean {
  return field instanceof HTMLTextAreaElement || (field instanceof HTMLInputElement && ["text", "search", "email", "url", "tel"].includes(field.type));
}

function snapshot(form: HTMLFormElement): string {
  return JSON.stringify([...new FormData(form).entries()].filter(([, v]) => typeof v === "string"));
}

/**
 * Profile settings that save themselves (David, 9 Nov 2026): a choice saves when it is made, and a typed field a moment
 * after the typing stops or when it is left, so nobody has to find a Save button at the foot of the page. The whole form
 * goes each time, called directly rather than submitted, so React never resets a field while someone is still typing in
 * it. A save that would change nothing is skipped. The state shows in a small note at the corner of the window.
 */
export function AutoSaveForm({ children, className }: { children: ReactNode; className?: string }) {
  const form = useRef<HTMLFormElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const last = useRef("");
  const [, start] = useTransition();
  const [state, setState] = useState<{ kind: "" | "saving" | "saved" | "error"; text: string }>({ kind: "", text: "" });

  useEffect(() => {
    if (form.current) last.current = snapshot(form.current);
    return () => window.clearTimeout(timer.current);
  }, []);

  useEffect(() => {
    if (state.kind !== "saved") return undefined;
    const done = window.setTimeout(() => setState({ kind: "", text: "" }), 2500);
    return () => window.clearTimeout(done);
  }, [state]);

  function save() {
    window.clearTimeout(timer.current);
    const el = form.current;
    if (!el) return;
    const now = snapshot(el);
    if (now === last.current) return;
    last.current = now;
    const data = new FormData(el);
    setState({ kind: "saving", text: "Saving..." });
    start(async () => {
      const result = await autoSaveProfileAction(data);
      if (!result.ok) last.current = "";   // the next change tries again
      setState(result.ok ? { kind: "saved", text: "Saved" } : { kind: "error", text: result.message });
    });
  }

  function changed(event: FormEvent<HTMLFormElement>) {
    const field = fieldOf(event.target);
    if (!field) return;
    if (!typed(field)) {
      save();
      return;
    }
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(save, PAUSE_MS);
  }

  return (
    <form
      ref={form}
      className={className}
      data-autosave="true"
      onSubmit={(event) => {   // Enter in a field saves now
        event.preventDefault();
        save();
      }}
      onChange={changed}
      onBlur={(event) => {
        const field = fieldOf(event.target);
        if (field && typed(field)) save();
      }}
    >
      {children}
      <p className={`autosave-state ${state.kind}`} role="status">
        {state.text}
      </p>
    </form>
  );
}
