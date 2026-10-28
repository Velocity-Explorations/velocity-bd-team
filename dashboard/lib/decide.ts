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

/** Notes from a Slack thread reply carry the member's Slack id (U08V7ULPH1N); the dashboard's carry a name. */
export function noteSource(by: string | null | undefined): "Slack thread reply" | "on the dashboard" {
  return by && /^[UW][A-Z0-9]{6,}$/.test(by) ? "Slack thread reply" : "on the dashboard";
}
