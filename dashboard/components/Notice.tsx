"use client";

import { X } from "lucide-react";
import { useState, type ReactNode } from "react";

const WORDS = { good: "Done", conflict: "Refused", info: "Note" } as const;

/**
 * A notice at the top of the content (PRO-569): the tone's wash, the word (Done, Refused, Note), one
 * sentence, at most one link, and a close button that also drops the notice from the address, so a
 * reload does not bring it back. Key it by its text, so a new notice opens again.
 */
export function Notice({ tone, children }: { tone: keyof typeof WORDS; children: ReactNode }) {
  const [open, setOpen] = useState(true);
  if (!open) return null;
  const close = () => {
    setOpen(false);
    const url = new URL(window.location.href);
    for (const key of ["notice", "error", "voted"]) url.searchParams.delete(key);
    window.history.replaceState(window.history.state, "", url);
  };
  return (
    <div className={`notice tone-${tone}`} role={tone === "conflict" ? "alert" : "status"}>
      <span className="notice-word">{WORDS[tone]}</span>
      <p>{children}</p>
      <button type="button" className="notice-close" aria-label="Close this notice" onClick={close}>
        <X aria-hidden="true" />
      </button>
    </div>
  );
}
