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

/** One of the Decide menu's choices: a submit button that is disabled while a decision saves, so it cannot be sent twice. */
export function DecideButton({ value, className, disabled = false, children }: {
  value: string;
  className: string;
  disabled?: boolean;
  children: ReactNode;
}) {
  const { pending } = useFormStatus();
  return (
    <button type="submit" name="status" value={value} className={className} disabled={disabled || pending}>
      {children}
    </button>
  );
}

/** Under the Decide button of the call a decision came back to: Saved, Already saved, or why nothing was saved. */
export function DecideOutcome({ callId }: { callId: string }) {
  const search = useSearchParams();
  const outcome = rowOutcome({ row: search.get("row"), notice: search.get("notice"), error: search.get("error") }, callId);
  if (!outcome) return null;
  return (
    <p className={`decide-outcome tone-${outcome.tone}`}>
      {outcome.tone === "good" ? <Check aria-hidden="true" /> : null}
      {outcome.text}
    </p>
  );
}
