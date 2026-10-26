// The filters and sort shared by the review queue and All calls: the filter bar (portals, tag, open
// or closed) and the column headers (sort, and each column's own filter). No imports, so
// `node --test` can load it directly.

export type CallState = "open" | "closed" | "";
export type SortKey = "seen" | "due" | "title" | "verdict" | "tier" | "decision" | "filter";
export type SortDir = "asc" | "desc";
export type Sort = { key: SortKey; dir: SortDir };
export type Params = Record<string, string | readonly string[]>;

/** Each column's first direction: newest first, closing soonest, A to Z, yes before no, tight
 *  before broad, pursue first, kept first. */
const NATURAL: Record<SortKey, SortDir> = {
  seen: "desc", due: "asc", title: "asc", verdict: "asc", tier: "asc", decision: "asc", filter: "asc",
};
export const SORT_KEYS = Object.keys(NATURAL) as SortKey[];
const DEFAULT_SORT: Sort = { key: "seen", dir: "desc" };

/**
 * A key ending in "_closed" set to true in calls.extra, the flag isClosed() reads, as a
 * regular expression both Postgres and JavaScript accept. Python's json.dumps writes ": ".
 */
export const CLOSED_PATTERN = '"[A-Za-z0-9_]+_closed": *true';

export type PortalOption = { name: string; calls: number };

/**
 * The Portals menu: every portal that has scanned, plus any with calls, by name, each with its
 * number of stored calls. A portal that scanned but had nothing open shows with 0 (PRO-563).
 */
export function portalOptions(scanned: readonly string[], counts: readonly { portal: string; calls: number }[]): PortalOption[] {
  const byName = new Map<string, number>();
  for (const name of scanned) if (name.trim()) byName.set(name.trim(), 0);
  for (const { portal, calls } of counts) if (portal.trim()) byName.set(portal.trim(), calls);
  return [...byName].map(([name, calls]) => ({ name, calls })).sort((a, b) => a.name.localeCompare(b.name));
}

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

/** The column to sort by and its direction; newest first unless a column this page has is asked for. */
export function pickSort(raw: string | string[] | undefined, rawDir: string | string[] | undefined,
                         allowed: readonly SortKey[] = SORT_KEYS): Sort {
  const value = Array.isArray(raw) ? raw[0] : raw;
  const key = SORT_KEYS.find((k) => k === value && allowed.includes(k));
  if (!key) return { ...DEFAULT_SORT };
  const dir = Array.isArray(rawDir) ? rawDir[0] : rawDir;
  return { key, dir: dir === "asc" || dir === "desc" ? dir : NATURAL[key] };
}

/** What a column's header sorts by when clicked: its own sort reversed, or that column from its start. */
export function nextSort(current: Sort, key: SortKey): Sort {
  if (current.key === key) return { key, dir: current.dir === "asc" ? "desc" : "asc" };
  return { key, dir: NATURAL[key] };
}

/** The sort as link params, leaving out the default and a column's natural direction. */
export function sortParams(sort: Sort): { sort: string; dir: string } {
  if (sort.key === DEFAULT_SORT.key && sort.dir === DEFAULT_SORT.dir) return { sort: "", dir: "" };
  return { sort: sort.key, dir: sort.dir === NATURAL[sort.key] ? "" : sort.dir };
}

/** A header's sort link: this view, sorted by the column (or reversed when it already is). `dir` is
 *  the column's direction now when it is the sort, else the one a click starts with. */
export function sortLink(base: string, params: Params, current: Sort, key: SortKey): { href: string; active: boolean; dir: SortDir } {
  const active = current.key === key;
  return { href: filterHref(base, { ...params, ...sortParams(nextSort(current, key)) }), active, dir: active ? current.dir : NATURAL[key] };
}

export type Choice = { value: string; label: string };
export type MenuItem = { label: string; href: string; active: boolean };

/** Whether the judges agree, in the Claude / Grok header's menu. */
export const JUDGE_CHOICES: Choice[] = [
  { value: "", label: "Any" },
  { value: "agree", label: "Claude and Grok agree" },
  { value: "disagree", label: "Claude and Grok disagree" },
];

/** A filter menu: one link per choice, each this view with only that filter changed. */
export function choiceLinks(base: string, params: Params, param: string, choices: Choice[], current: string): MenuItem[] {
  return choices.map((c) => ({ label: c.label, href: filterHref(base, { ...params, [param]: c.value }), active: c.value === current }));
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
