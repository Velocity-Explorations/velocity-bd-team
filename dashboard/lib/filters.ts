// The filter panel shared by the review queue and All calls: which portals, open or closed,
// and the sort order. No imports, so `node --test` can load it directly.

export type CallState = "open" | "closed" | "";
export type Sort = "newest" | "due";

/**
 * A key ending in "_closed" set to true in calls.extra, the flag isClosed() reads, as a
 * regular expression both Postgres and JavaScript accept. Python's json.dumps writes ": ".
 */
export const CLOSED_PATTERN = '"[A-Za-z0-9_]+_closed": *true';

/** Every known value of a repeated search param (?portal=a&portal=b), trimmed, once each. */
export function pickMany(raw: string | string[] | undefined, known: readonly string[], max = 50): string[] {
  const values = (Array.isArray(raw) ? raw : raw === undefined ? [] : [raw]).map((v) => v.trim());
  const picked: string[] = [];
  for (const value of values) {
    if (value && known.includes(value) && !picked.includes(value)) picked.push(value);
    if (picked.length >= max) break;
  }
  return picked;
}

/** "open", "closed", or "" for both. `legacyOpen` keeps links from before the panel (?open=1) working. */
export function pickState(state: string | string[] | undefined, legacyOpen?: string | string[] | undefined): CallState {
  const value = Array.isArray(state) ? state[0] : state;
  if (value === "open" || value === "closed") return value;
  const legacy = Array.isArray(legacyOpen) ? legacyOpen[0] : legacyOpen;
  return legacy === "1" ? "open" : "";
}

/** Newest first unless "due" (closing soonest) is asked for. */
export function pickSort(raw: string | string[] | undefined): Sort {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value === "due" ? "due" : "newest";
}

/** A link to `base` with these params; list values repeat their key, and empty values are left out. */
export function filterHref(base: string, params: Record<string, string | readonly string[] | null | undefined>): string {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    for (const item of typeof value === "string" ? [value] : (value ?? [])) {
      if (item) query.append(key, item);
    }
  }
  const text = query.toString();
  return text ? `${base}?${text}` : base;
}
