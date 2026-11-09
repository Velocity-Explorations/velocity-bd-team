// The Fit ratings page (PRO-487): each tag, keyword and NAICS code with what the ledger holds about it, and the team's
// rating. review/fit.py scores calls from these, so the keys match its keys. No imports, so `node --test` can load it.

export const RATINGS = ["core", "good", "neutral", "poor", "never"] as const;
export type Rating = (typeof RATINGS)[number];

/** The scale, best first, with its points and what it means. */
export const SCALE: { key: Rating; label: string; points: string; tone: string; means: string }[] = [
  { key: "core", label: "Core", points: "+2", tone: "good", means: "We want nearly every call like this." },
  { key: "good", label: "Good", points: "+1", tone: "good", means: "Usually worth a look." },
  { key: "neutral", label: "Neutral", points: "0", tone: "neutral", means: "Tells us nothing either way." },
  { key: "poor", label: "Poor", points: "-1", tone: "warn", means: "Usually not for us." },
  { key: "never", label: "Never", points: "", tone: "bad", means: "We don't pursue it, whatever else the call has." },
];

/** The rating slider's five stops, low to high, as a tuning control reads (David, 9 Nov 2026). */
export const SLIDER = [...SCALE].reverse();
const NEUTRAL_STOP = 2;

/** Where a rating sits on the slider; a row nobody rated sits at Neutral. */
export function stopOf(rating: string | null | undefined): number {
  const at = SLIDER.findIndex((s) => s.key === rating);
  return at < 0 ? NEUTRAL_STOP : at;
}

/** The rating at a slider position, held to the five stops. */
export function ratingAt(stop: number): Rating {
  if (Number.isNaN(stop)) return SLIDER[NEUTRAL_STOP].key;
  return SLIDER[Math.min(SLIDER.length - 1, Math.max(0, Math.round(stop)))].key;
}

export type FitSection = "work" | "customer" | "type" | "access" | "keyword" | "naics";

/** The page's sections in order, with the question each one's rating answers. */
export const SECTIONS: { key: FitSection; label: string; question: string; hint?: string }[] = [
  {
    key: "work",
    label: "Work",
    question: "When this is the primary focus of a call, the work that is most of what the buyer wants",
    hint: "A Never here rules a call out only when the judges agree this is its primary focus.",
  },
  { key: "customer", label: "Customer", question: "When the call comes from this buyer" },
  { key: "type", label: "Type", question: "When the call is this kind of opportunity" },
  { key: "access", label: "Access", question: "When the call comes with this condition" },
  {
    key: "keyword",
    label: "Keywords",
    question: "When a call holds this keyword as a whole word",
    hint: "A keyword only moves the score a little, and a Never here does not rule a call out.",
  },
  {
    key: "naics",
    label: "NAICS",
    question: "When the call lists this code",
    hint: "Codes in sectors 51, 54 and 92 are rated one by one. Every other code is rated through its sector. A Never rules a call out.",
  },
];

const NAICS_TITLES: Record<string, string> = {
  "236210": "Industrial building construction",
  "236220": "Commercial and institutional building construction",
  "237310": "Highway, street and bridge construction",
  "238160": "Roofing contractors",
  "238210": "Electrical contractors and other wiring installation",
  "238220": "Plumbing, heating and air-conditioning contractors",
  "238290": "Other building equipment contractors",
  "325120": "Industrial gas manufacturing",
  "325920": "Explosives manufacturing",
  "332710": "Machine shops",
  "332721": "Precision turned product manufacturing",
  "332999": "All other miscellaneous fabricated metal products",
  "334511": "Search, detection, navigation and guidance instrument manufacturing",
  "334516": "Analytical laboratory instrument manufacturing",
  "335910": "Battery manufacturing",
  "336414": "Guided missile and space vehicle manufacturing",
  "481212": "Nonscheduled chartered freight air transportation",
  "488190": "Other support activities for air transportation",
  "517810": "All other telecommunications",
  "523210": "Securities and commodity exchanges",
  "541330": "Engineering services",
  "541380": "Testing laboratories and services",
  "541511": "Custom computer programming services",
  "541512": "Computer systems design services",
  "541513": "Computer facilities management services",
  "541519": "Other computer related services",
  "541611": "Administrative and general management consulting",
  "541612": "Human resources consulting services",
  "541614": "Process, physical distribution and logistics consulting",
  "541620": "Environmental consulting services",
  "541690": "Other scientific and technical consulting services",
  "541714": "R&D in biotechnology (except nanobiotechnology)",
  "541715": "R&D in the physical, engineering and life sciences (except nano and biotech)",
  "541820": "Public relations agencies",
  "541990": "All other professional, scientific and technical services",
  "561210": "Facilities support services",
  "561612": "Security guards and patrol services",
  "561621": "Security systems services (except locksmiths)",
  "561720": "Janitorial services",
  "561990": "All other support services",
  "611420": "Computer training",
  "621910": "Ambulance services",
  "811210": "Electronic and precision equipment repair and maintenance",
  "811310": "Commercial and industrial machinery repair and maintenance",
  "927110": "Space research and technology",
};

const SECTOR_NAMES: Record<string, string> = {
  "11": "Agriculture", "21": "Mining", "22": "Utilities", "23": "Construction", "31-33": "Manufacturing", "42": "Wholesale trade",
  "44-45": "Retail trade", "48-49": "Transportation", "52": "Finance", "53": "Real estate", "55": "Management of companies",
  "56": "Administrative, support and facilities services", "61": "Education", "62": "Health care", "71": "Arts and recreation",
  "72": "Accommodation and food", "81": "Repair and maintenance",
};

/** Sectors whose codes are rated one by one, because the code itself tells software from the rest. */
const OWN_CODE_SECTORS = ["51", "54", "92"];
const SECTOR_RANGES = ["31-33", "44-45", "48-49"];

/** A name as the ratings key it: "AI and ML" is ai-and-ml, the same as review/fit.py. */
export function slug(text: string): string {
  return text.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
}

/** The NAICS sector of a code: 236220 is 23, 325120 is 31-33. */
export function sectorOf(code: string): string {
  const two = code.slice(0, 2);
  for (const range of SECTOR_RANGES) {
    const [low, high] = range.split("-");
    if (two >= low && two <= high) return range;
  }
  return two;
}

const KEY_SHAPE = /^(work|customer|type|access|keyword|naics|naics-sector|notice)\.[a-z0-9-]+$/;

/** A rating's key if it is well formed, with the section it belongs to; null otherwise. */
export function sectionOfKey(key: string): FitSection | null {
  if (!KEY_SHAPE.test(key)) return null;
  const prefix = key.slice(0, key.indexOf("."));
  if (prefix === "naics-sector") return "naics";
  if (prefix === "notice") return "type";
  return prefix as FitSection;
}

export function isRating(value: unknown): value is Rating {
  return typeof value === "string" && (RATINGS as readonly string[]).includes(value);
}

export type RatingRow = { key: string; section: string; name: string; rating: string; note: string | null; loaded_at: string; changed_by: string | null };
export type TagRow = { name: string; tag_group: string; covers: string | null };
export type EvidenceCall = {
  id: string; title: string | null; url: string | null; type: string | null; naics_code: string | null;
  matched_keywords: string | null; human_status: string | null;
};
export type CallTag = { call_id: string; tag: string };
export type JudgeRow = { call_id: string; judge: string; verdict: string; main_work: string | null };

/** Three counts: yes, maybe, no. */
export type Mix = [number, number, number];
export type Example = { id: string; title: string; url: string | null; team: string | null; claude: string | null; grok: string | null };
export type FitRow = {
  key: string;
  section: FitSection;
  name: string;
  covers: string;
  kind: "" | "notice" | "sector";
  rating: Rating | null;
  note: string;
  changedBy: string | null;
  changedAt: string | null;
  calls: number;
  mainWork: number | null;
  claude: Mix;
  grok: Mix;
  team: [string, number][];
  examples: Example[];
  codes: { code: string; title: string; calls: number }[];
};

const NOTICE_COVERS: Record<string, string> = {
  "notice.special-notice": "SAM.gov's catch-all notice: industry days, intents to sole-source, general announcements",
  "notice.presolicitation": "SAM.gov's notice that a solicitation is coming",
};
const VERDICT_PLACE: Record<string, number> = { yes: 0, maybe: 1, no: 2 };
const TEAM_RANK: Record<string, number> = { pursue: 0, submitted: 1, not_relevant: 2, dismissed: 3 };
const VERDICT_RANK: Record<string, number> = { yes: 0, maybe: 1, no: 2 };

function keywordsOf(call: EvidenceCall): string[] {
  try {
    const parsed: unknown = JSON.parse(call.matched_keywords ?? "[]");
    return Array.isArray(parsed) ? parsed.map(String) : [];
  } catch {
    return [];
  }
}

/**
 * Every row the page shows: whatever has a rating, plus any tag, keyword or NAICS code the ledger holds that nobody has
 * rated yet, so something new shows up to be rated. In each section unrated rows come first, then tags in the list's
 * order, and keywords and codes with the most calls first.
 */
export function buildFitRows(input: { ratings: RatingRow[]; tags: TagRow[]; calls: EvidenceCall[]; callTags: CallTag[]; judges: JudgeRow[] }): FitRow[] {
  const newest = new Map<string, Map<string, JudgeRow>>();
  for (const row of input.judges) {
    if (!newest.has(row.call_id)) newest.set(row.call_id, new Map());
    newest.get(row.call_id)?.set(row.judge, row);   // rows come oldest first, so the newest stands
  }
  const callById = new Map(input.calls.map((c) => [c.id, c]));
  const members = new Map<string, Set<string>>();
  const join = (key: string, callId: string) => {
    if (!members.has(key)) members.set(key, new Set());
    members.get(key)?.add(callId);
  };
  const groupOf = new Map(input.tags.map((t) => [t.name, t.tag_group]));
  for (const row of input.callTags) {
    const group = groupOf.get(row.tag);
    if (group) join(`${group}.${slug(row.tag)}`, row.call_id);
  }
  const ratingByKey = new Map(input.ratings.map((r) => [r.key, r]));
  const codeCalls = new Map<string, number>();
  for (const call of input.calls) {
    for (const word of keywordsOf(call)) join(`keyword.${slug(word)}`, call.id);
    const code = (call.naics_code ?? "").trim();
    if (code) {
      codeCalls.set(code, (codeCalls.get(code) ?? 0) + 1);
      const own = OWN_CODE_SECTORS.includes(code.slice(0, 2)) || ratingByKey.has(`naics.${code}`);
      join(own ? `naics.${code}` : `naics-sector.${sectorOf(code)}`, call.id);
    }
    const notice = `notice.${slug(call.type ?? "")}`;
    if (ratingByKey.has(notice)) join(notice, call.id);
  }
  const mainCounts = new Map<string, Set<string>>();
  for (const [callId, judges] of newest) {
    for (const row of judges.values()) {
      if (!row.main_work) continue;
      const key = `work.${slug(row.main_work)}`;
      if (!mainCounts.has(key)) mainCounts.set(key, new Set());
      mainCounts.get(key)?.add(callId);
    }
  }

  const rowFor = (key: string, section: FitSection, name: string, covers: string, kind: FitRow["kind"]): FitRow => {
    const rated = ratingByKey.get(key);
    const ids = [...(members.get(key) ?? [])].filter((id) => callById.has(id));
    const claude: Mix = [0, 0, 0];
    const grok: Mix = [0, 0, 0];
    const team = new Map<string, number>();
    for (const id of ids) {
      const verdicts = newest.get(id);
      const c = verdicts?.get("claude")?.verdict;
      const g = verdicts?.get("grok")?.verdict;
      if (c && c in VERDICT_PLACE) claude[VERDICT_PLACE[c]] += 1;
      if (g && g in VERDICT_PLACE) grok[VERDICT_PLACE[g]] += 1;
      const status = callById.get(id)?.human_status;
      if (status) team.set(status, (team.get(status) ?? 0) + 1);
    }
    const score = (id: string) => {
      const verdicts = newest.get(id);
      const status = callById.get(id)?.human_status;
      return [
        status ? TEAM_RANK[status] ?? 4 : 5,
        (VERDICT_RANK[verdicts?.get("claude")?.verdict ?? ""] ?? 3) + (VERDICT_RANK[verdicts?.get("grok")?.verdict ?? ""] ?? 3),
      ];
    };
    const examples = [...ids]
      .sort((a, b) => {
        const [ta, va] = score(a);
        const [tb, vb] = score(b);
        return ta - tb || va - vb || a.localeCompare(b);
      })
      .slice(0, 3)
      .map((id) => {
        const call = callById.get(id);
        return {
          id, title: call?.title ?? id, url: call?.url ?? null, team: call?.human_status ?? null,
          claude: newest.get(id)?.get("claude")?.verdict ?? null, grok: newest.get(id)?.get("grok")?.verdict ?? null,
        };
      });
    return {
      key, section, name: rated?.name ?? name, covers, kind,
      rating: isRating(rated?.rating) ? rated.rating : null,
      note: rated?.note ?? "",
      changedBy: rated?.changed_by ?? null,
      changedAt: rated?.changed_by ? rated.loaded_at : null,
      calls: ids.length,
      mainWork: section === "work" ? mainCounts.get(key)?.size ?? 0 : null,
      claude, grok,
      team: [...team].sort((a, b) => b[1] - a[1]),
      examples,
      codes: kind === "sector"
        ? [...codeCalls].filter(([code]) => sectorOf(code) === key.slice("naics-sector.".length) && !ratingByKey.has(`naics.${code}`))
            .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
            .map(([code, calls]) => ({ code, title: NAICS_TITLES[code] ?? "", calls }))
        : [],
    };
  };

  const rows: FitRow[] = [];
  const seen = new Set<string>();
  const add = (row: FitRow) => {
    if (!seen.has(row.key)) rows.push(row);
    seen.add(row.key);
  };
  const listed = (group: FitSection) => input.tags.filter((t) => t.tag_group === group)
    .map((t) => rowFor(`${group}.${slug(t.name)}`, group, t.name, t.covers ?? "", ""));
  const unratedFirst = (list: FitRow[]) => [...list.filter((r) => !r.rating), ...list.filter((r) => r.rating)];
  const mostCalls = (list: FitRow[]) => [...list].sort((a, b) => b.calls - a.calls || a.name.localeCompare(b.name));

  for (const group of ["work", "customer", "type", "access"] as const) {
    const notices = group === "type"
      ? input.ratings.filter((r) => r.key.startsWith("notice.")).map((r) => rowFor(r.key, "type", r.name, NOTICE_COVERS[r.key] ?? "", "notice"))
      : [];
    unratedFirst([...listed(group), ...notices]).forEach(add);
  }

  const words = new Map<string, string>();
  for (const call of input.calls) for (const word of keywordsOf(call)) words.set(`keyword.${slug(word)}`, word);
  for (const rated of input.ratings) if (rated.key.startsWith("keyword.")) words.set(rated.key, rated.name);
  unratedFirst(mostCalls([...words].map(([key, word]) => {
    const code = /^\d{6}$/.test(word) ? `NAICS ${word}${NAICS_TITLES[word] ? `: ${NAICS_TITLES[word]}` : ""}` : "";
    return rowFor(key, "keyword", word, code, "");
  }))).forEach(add);

  const codes = new Set<string>();
  for (const key of members.keys()) if (key.startsWith("naics.")) codes.add(key.slice("naics.".length));
  for (const rated of input.ratings) if (rated.key.startsWith("naics.")) codes.add(rated.key.slice("naics.".length));
  const sectors = new Set<string>();
  for (const key of members.keys()) if (key.startsWith("naics-sector.")) sectors.add(key.slice("naics-sector.".length));
  for (const rated of input.ratings) if (rated.key.startsWith("naics-sector.")) sectors.add(rated.key.slice("naics-sector.".length));
  unratedFirst([
    ...mostCalls([...codes].map((code) => rowFor(`naics.${code}`, "naics", code, NAICS_TITLES[code] ?? "", ""))),
    ...mostCalls([...sectors].map((sector) => rowFor(
      `naics-sector.${sector}`, "naics", `${sector} ${SECTOR_NAMES[sector] ?? "Other"}`, "Stands for every code in the sector with no rating of its own.", "sector",
    ))),
  ]).forEach(add);
  return rows;
}
