// What Start the draft suggests (David, 7 Nov 2026): Claude's recommendation for a call, read from draft_suggestions,
// to fill the dialog in for the person to change. No imports, so `node --test` can load it directly.

export type Suggestion = {
  format: string | null;
  formatWhy: string;
  approvalMode: "every_step" | "key_gates" | null;
  approvalWhy: string;
  direction: string;
  buildsOn: { id: string; why: string }[];
};
export type SuggestionRow = { id: number; state: string; suggestion: string | null; note: string | null; answered_at: string | null };

const OFFLINE_MS = 2 * 60 * 1000;
const text = (v: unknown): string => (typeof v === "string" ? v.trim() : "");

/** A stored suggestion, keeping only the formats and the past work the dialog offers; null when it cannot be read. */
export function parseSuggestion(json: string | null | undefined, formats: string[], itemIds: Set<string>): Suggestion | null {
  let value: unknown;
  try {
    value = JSON.parse(json ?? "");
  } catch {
    return null;
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  const v = value as Record<string, unknown>;
  const mode = v.approval_mode === "every_step" || v.approval_mode === "key_gates" ? v.approval_mode : null;
  const buildsOn = Array.isArray(v.builds_on)
    ? v.builds_on.flatMap((b) => {
        if (!b || typeof b !== "object") return [];
        const { id, why } = b as Record<string, unknown>;
        return typeof id === "string" && itemIds.has(id) ? [{ id, why: text(why) }] : [];
      })
    : [];
  return {
    format: typeof v.format === "string" && formats.includes(v.format) ? v.format : null,
    formatWhy: text(v.format_why),
    approvalMode: mode,
    approvalWhy: text(v.approval_why),
    direction: text(v.direction),
    buildsOn,
  };
}

/** The Builds on groups with Claude's picks first, in its order, and out of their usual group. */
export function withSuggestedFirst<T extends { id: string }>(groups: { title: string; items: T[] }[], picked: string[]): { title: string; items: T[] }[] {
  if (!picked.length) return groups;
  const byId = new Map(groups.flatMap((g) => g.items.map((i) => [i.id, i] as const)));
  const first = picked.map((id) => byId.get(id)).filter((i): i is T => Boolean(i));
  if (!first.length) return groups;
  const rest = groups.map((g) => ({ title: g.title, items: g.items.filter((i) => !picked.includes(i.id)) })).filter((g) => g.items.length);
  return [{ title: "Suggested by Claude", items: first }, ...rest];
}

/** What a waiting suggestion says while the person waits. */
export function suggestStatus(state: string, seenAt: string | null, now: number = Date.now()): string {
  if (state !== "queued" && state !== "working") return "";
  const seen = seenAt ? Date.parse(seenAt) : Number.NaN;
  if (Number.isNaN(seen) || now - seen > OFFLINE_MS) return "The assistant is offline, so the suggestion waits until it is back";
  return "Claude is reading the call and your past work, about half a minute";
}
