// The Decide cell's words (Q9, Q14, PRO-572) and where a note came from. No imports, so
// `node --test` can load it directly.

export type VoteLike = { person: string; status: string; decided_at: string };

/** The viewer's latest decision on a call, from its votes; null when they have not decided it. */
export function yourVote<T extends VoteLike>(votes: T[], viewer: string | null): T | null {
  if (!viewer) return null;
  return votes.find((v) => v.person === viewer) ?? null;
}

/** Decide on an undecided call, Change your own decision, Add yours beside someone else's (C5, Q14). */
export function decideLabel(input: { yours: VoteLike | null; callStatus: string | null }): "Decide" | "Change" | "Add yours" {
  if (input.yours) return "Change";
  return input.callStatus ? "Add yours" : "Decide";
}

/** Under a needs your decision badge: due today, due tomorrow or due in N days, within 14 days. */
export function dueLine(daysLeft: number | null): string {
  if (daysLeft === null || daysLeft < 0 || daysLeft > 14) return "";
  if (daysLeft === 0) return "due today";
  if (daysLeft === 1) return "due tomorrow";
  return `due in ${daysLeft} days`;
}

/**
 * The id of a call's row (Task 1, 18 Nov 2026), so a decision comes back to the row it was made on: `call-` and the call
 * id with anything but letters, digits, `_` and `-` replaced, safe as an HTML id and in a URL's fragment.
 */
export function rowAnchor(callId: string): string {
  return `call-${callId.replace(/[^A-Za-z0-9_-]/g, "_")}`;
}

/**
 * What the Decide cell of the call a decision came back to says (Task 1, 18 Nov 2026): `row` names that call, and the
 * notice or error is what the decision did. Saved, Already saved, or the reason nothing was saved, beside the button the
 * person used, since the notice at the top of the page can be out of view.
 */
export function rowOutcome(params: { row?: string | null; notice?: string | null; error?: string | null }, callId: string):
  { tone: "good" | "conflict"; text: string } | null {
  if (!params.row || params.row !== callId) return null;
  if (params.error) return { tone: "conflict", text: params.error };
  if (params.notice) return { tone: "good", text: params.notice.startsWith("Already saved") ? "Already saved" : "Saved" };
  return null;
}

/** Notes from a Slack thread reply carry the member's Slack id (U08V7ULPH1N); the dashboard's carry a name. */
export function noteSource(by: string | null | undefined): "Slack thread reply" | "on the dashboard" {
  return by && /^[UW][A-Z0-9]{6,}$/.test(by) ? "Slack thread reply" : "on the dashboard";
}

/**
 * Why a call Claude liked is not for Velocity (David, 5 Nov): the reason a Not relevant decision carries as its note.
 * The judges' examples show the team's note in place of Claude's own reasoning (review/feedback.py), so a reason is
 * what tells them which part made the whole call wrong. In order: the work, the customer, the listing, the time. Six
 * were added on 16 Nov from David's own notes on that week's Top 10 (too large, too specialized) and his calls on the
 * rest; a key, once used, keeps its meaning, since notes in the ledger carry its label. "umbrella" (Umbrella
 * announcement only) left the list the same day: it is a listing tag now (lib/listing.ts listingChoice), not a reason.
 */
export const NOT_RELEVANT_REASONS = [
  { key: "large", label: "Too large for Velocity" },
  { key: "specialized", label: "Too specialized for Velocity" },
  { key: "hardware", label: "Mostly hardware" },
  { key: "cyber", label: "Cyber or enterprise IT" },
  { key: "staffing", label: "Staffing or IT support" },
  { key: "eligibility", label: "Wrong customer or eligibility" },
  { key: "broad", label: "Too broad, no clear fit" },
  { key: "planning", label: "Planning only, no award" },
  { key: "award", label: "Award or sole-source notice" },
  { key: "time", label: "Too little time to respond" },
] as const;

/** Not relevant asks for a reason only where it disagrees with Claude: a call it rated yes or maybe. */
export function asksReason(verdict: string | null): boolean {
  return verdict === "yes" || verdict === "maybe";
}

/** A Decide button's value: the decision, and for Not relevant the reason's key ("not_relevant:hardware", or "other"). */
export function readChoice(raw: unknown): { status: string | null; reason: string | null } {
  if (typeof raw !== "string" || !raw) return { status: null, reason: null };
  const [status, key = ""] = raw.split(":", 2);
  const known = key === "other" || NOT_RELEVANT_REASONS.some((r) => r.key === key);
  return { status, reason: status === "not_relevant" && known ? key : null };
}

/** The note a reason leaves: its label, then the person's own words; with Other, their words alone. */
export function reasonNote(reason: string | null, words: string): string {
  const own = words.trim();
  const label = NOT_RELEVANT_REASONS.find((r) => r.key === reason)?.label;
  if (!label) return own;
  return own ? `${label}: ${own}` : label;
}
