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

export type DecisionPlan = "decide" | "add" | "note" | "noop";

/**
 * What saving a decision does, given the call's decision (`current`), the person's own latest
 * decision on the call (`mine`, null if they have not decided it) and whether the call's
 * decision must stay as it is (`keepCallDecision`: the review queue while everyone decides
 * every call). "decide" sets the call's decision and records the person's; "add" records the
 * person's beside the call's, which stays; "note" only appends the note.
 */
export function planDecision(
  current: Decision | null,
  chosen: Decision,
  note: string,
  mine: string | null,
  keepCallDecision = false,
): DecisionPlan {
  if (current === null || (chosen !== current && !keepCallDecision)) return "decide";
  if (chosen !== mine) return "add";
  return note.trim() ? "note" : "noop";
}

export type QueueMode = "each" | "shared";

/**
 * DASHBOARD_QUEUE. "each" (the default, for the training phase): a call stays in each person's
 * review queue until they decide it. "shared": the first decision takes it off everyone's.
 */
export function pickQueueMode(raw: string | undefined): QueueMode {
  return raw?.trim().toLowerCase() === "shared" ? "shared" : "each";
}

/** A search-param value if it is one of `allowed`, else "". */
export function pickAllowed<T extends string>(raw: string | string[] | undefined, allowed: readonly T[]): T | "" {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value !== undefined && (allowed as readonly string[]).includes(value) ? (value as T) : "";
}
