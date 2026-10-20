// The ledger's allowed column values (see docs/LEDGER_SCHEMA.md). No imports.

export const VERDICTS = ["yes", "maybe", "no"] as const;
export const HUMAN_STATUSES = ["pursue", "not_relevant", "submitted", "dismissed"] as const;
export const FILTER_RESULTS = ["pending", "kept", "rejected"] as const;

export type Decision = (typeof HUMAN_STATUSES)[number];

/** The four triage decisions, in button order. */
export const DECISIONS: { value: Decision; label: string }[] = [
  { value: "pursue", label: "Pursue" },
  { value: "not_relevant", label: "Not relevant" },
  { value: "submitted", label: "Submitted" },
  { value: "dismissed", label: "Dismiss" },
];

export const STATUS_LABELS: Record<Decision, string> = {
  pursue: "Pursue",
  not_relevant: "Not relevant",
  submitted: "Submitted",
  dismissed: "Dismissed",
};

export function isDecision(value: unknown): value is Decision {
  return typeof value === "string" && (HUMAN_STATUSES as readonly string[]).includes(value);
}

export type DecisionPlan = "decide" | "agree" | "note" | "noop";

/**
 * What saving a decision form does, given the decision the page showed (`expected`) and the
 * person's own latest decision on the call (`mine`, null if they have not decided it):
 * a different decision changes the call's decision; the same decision, when it is someone
 * else's, adds theirs beside it; otherwise a note is only appended.
 */
export function planDecision(expected: Decision | null, chosen: Decision, note: string, mine: string | null): DecisionPlan {
  if (chosen !== expected) return "decide";
  if (chosen !== mine) return "agree";
  return note.trim() ? "note" : "noop";
}

/** A search-param value if it is one of `allowed`, else "". */
export function pickAllowed<T extends string>(raw: string | string[] | undefined, allowed: readonly T[]): T | "" {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value !== undefined && (allowed as readonly string[]).includes(value) ? (value as T) : "";
}
