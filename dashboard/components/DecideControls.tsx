"use client";

import { Check, LoaderCircle } from "lucide-react";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";
import { useFormStatus } from "react-dom";
import { rowOutcome } from "@/lib/decide";

// The Decide menu's client parts (Task 1, 18 Nov 2026). On 9 Nov a Pursue saved on the first click but looked as if it
// had not: nothing showed while it went over a slow link, and the answer came back as a notice at the top of the page,
// away from the row. While a decision saves, the button says Saving and the menu cannot be chosen again; afterwards the
// row's Decide cell says what happened.

/** The Decide button's words: its label, or Saving while the decision is on its way. */
export function DecideLabel({ label }: { label: string }) {
  const { pending } = useFormStatus();
  if (!pending) return <>{label}</>;
  return (
    <>
      <LoaderCircle className="spin" aria-hidden="true" />
      Saving...
    </>
  );
}

/**
 * One of a form's choices: a submit button that is disabled while the form saves, so it cannot be sent twice. The Decide
 * menu's (name `status`), and a Top 10 pick's rating (name `rating`, with `pressed` for the person's own, Task 5).
 */
export function DecideButton({ value, className, disabled = false, name = "status", pressed, children }: {
  value: string;
  className: string;
  disabled?: boolean;
  name?: string;
  pressed?: boolean;
  children: ReactNode;
}) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" name={name} value={value} className={className} disabled={disabled || pending} aria-pressed={pressed}>
      {children}
    </button>
  );
}

/**
 * Under a row's control, on the row a write came back to: Saved, Already saved, or why nothing was saved. `param` names
 * the address key that holds the row's call: `row` for a decision, `rated` for a Top 10 pick's rating (Task 5).
 */
export function RowOutcome({ callId, param = "row", className = "decide-outcome" }: { callId: string; param?: string; className?: string }) {
  const search = useSearchParams();
  const outcome = rowOutcome({ row: search.get(param), notice: search.get("notice"), error: search.get("error") }, callId);
  if (!outcome) return null;
  return (
    <p className={`${className} tone-${outcome.tone}`}>
      {outcome.tone === "good" ? <Check aria-hidden="true" /> : null}
      {outcome.text}
    </p>
  );
}

/** Under the Decide button of the call a decision came back to. */
export function DecideOutcome({ callId }: { callId: string }) {
  return <RowOutcome callId={callId} />;
}
