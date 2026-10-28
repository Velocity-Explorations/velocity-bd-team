// Home's pieces (PRO-570): days left in words, the waiting requests by kind, a short date, each
// portal's logo, and the Top 10's order. No imports, so `node --test` can load it directly.

/** "3 days left", "closes today", "closed 2 days ago". Empty when the deadline is unknown. */
export function daysLeftText(days: number | null): string {
  if (days === null) return "";
  if (days === 0) return "closes today";
  if (days === 1) return "1 day left";
  if (days > 1) return `${days} days left`;
  if (days === -1) return "closed yesterday";
  return `closed ${-days} days ago`;
}

const KINDS: Record<string, [string, string]> = {
  keyword_change: ["a keyword change", "keyword changes"],
  rereview: ["a re-review", "re-reviews"],
  scan: ["a scan", "scans"],
  draft: ["a draft", "drafts"],
  fault_report: ["a fault report", "fault reports"],
};

/** The requests waiting, by kind in the order first seen: "a keyword change, a scan", "2 scans". */
export function kindsLine(kinds: string[]): string {
  const counts = new Map<string, number>();
  for (const kind of kinds) counts.set(kind, (counts.get(kind) ?? 0) + 1);
  return [...counts]
    .map(([kind, n]) => {
      const [one, many] = KINDS[kind] ?? [`a ${kind} request`, `${kind} requests`];
      return n === 1 ? one : `${n} ${many}`;
    })
    .join(", ");
}

/** "11 Nov" in the given IANA zone. */
export function dayMonth(date: Date, timeZone: string): string {
  let parts: Intl.DateTimeFormatPart[];
  try {
    parts = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone }).formatToParts(date);
  } catch {
    parts = new Intl.DateTimeFormat("en-GB", { day: "numeric", month: "short", timeZone: "UTC" }).formatToParts(date);
  }
  const part = (type: string) => parts.find((p) => p.type === type)?.value ?? "";
  return `${part("day")} ${part("month")}`;
}

/** The portals with a logo in public/logos; the rest show an initials tile. */
const LOGOS: Record<string, string> = {
  AFWERX: "afwerx",
  DIU: "diu",
  "NASA Forecast": "nasa",
  NSTXL: "nstxl",
  "SAM.gov": "sam-gov",
  SpaceWERX: "spacewerx",
  "SSC Front Door": "ssc",
  "Vulcan SOF": "vulcan-sof",
};
const TILES: Record<string, string> = { "DOE SBIR": "DOE", "Space Florida": "SF", APFIT: "AP" };

export function portalLogo(portal: string): { src: string } | { initials: string } {
  const file = LOGOS[portal];
  if (file) return { src: `/logos/${file}.png` };
  const tile = TILES[portal];
  if (tile) return { initials: tile };
  const words = portal.trim().split(/\s+/).filter(Boolean);
  return { initials: words.slice(0, 2).map((w) => w[0].toUpperCase()).join("") || "?" };
}

/** The brief's Top 10 order, without calls the ledger no longer has. */
export function topTenOrder(ids: string[], known: Set<string>): string[] {
  return ids.filter((id) => known.has(id));
}
