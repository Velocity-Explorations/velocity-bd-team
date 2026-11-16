// The ledger's allowed column values (see docs/LEDGER_SCHEMA.md). No imports.

export const VERDICTS = ["yes", "maybe", "no"] as const;
export const HUMAN_STATUSES = ["pursue", "not_relevant", "submitted", "dismissed"] as const;
export const FILTER_RESULTS = ["pending", "kept", "rejected"] as const;

export type Decision = (typeof HUMAN_STATUSES)[number];

/**
 * What a person can say about a call: the call's four decisions, and Unsure (David, 16 Nov 2026, migration 020), which
 * holds the call for the team. Unsure is a vote in `decisions` only; the call's own decision (human_status) never
 * takes it, so the call waits under Calls' Unsure view until someone decides it.
 */
export const VOTES = [...HUMAN_STATUSES, "unsure"] as const;
export type Vote = (typeof VOTES)[number];

/** The Decide menu, in button order. */
export const DECISIONS: { value: Vote; label: string }[] = [
  { value: "pursue", label: "Pursue" },
  { value: "not_relevant", label: "Not relevant" },
  { value: "unsure", label: "Unsure" },
  { value: "submitted", label: "Submitted" },
  { value: "dismissed", label: "Dismiss" },
];

export const STATUS_LABELS: Record<Vote, string> = {
  pursue: "Pursue",
  not_relevant: "Not relevant",
  unsure: "Unsure",
  submitted: "Submitted",
  dismissed: "Dismissed",
};

export function isDecision(value: unknown): value is Decision {
  return typeof value === "string" && (HUMAN_STATUSES as readonly string[]).includes(value);
}

export function isVote(value: unknown): value is Vote {
  return typeof value === "string" && (VOTES as readonly string[]).includes(value);
}

/**
 * What Unsure does, given the person's own latest vote (`mine`) and whether the call's decision is theirs (`own`).
 * "clear" takes their decision off the call, which then waits for the team again; "add" records their Unsure beside
 * whatever the call has; "note" only appends the note to an Unsure they already gave.
 */
export function unsurePlan(input: { mine: string | null; note: string; own: boolean }): "clear" | "add" | "note" | "noop" {
  if (input.mine === "unsure") return input.note.trim() ? "note" : "noop";
  return input.own ? "clear" : "add";
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

/**
 * Whether a decision only adds the person's vote, leaving the call's decision as it is: one made from the review queue
 * while everyone decides every call, once the call has a decision, unless that decision is the person's own. Changing
 * your own mind changes the call (David, 16 Nov 2026: Pursue then Not relevant on Home's Top 10 left E-ICAM, JVCC and
 * ERIS at Pursue, so they sat in Proposals' To draft). `aliases` are the names the person's decisions are under.
 */
export function keepsCallDecision(keepFlag: boolean, history: boolean, decidedBy: string | null, aliases: string[]): boolean {
  return keepFlag && history && !(decidedBy !== null && aliases.includes(decidedBy));
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
