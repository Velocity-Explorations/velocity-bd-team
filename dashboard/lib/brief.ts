// The Monday brief as the weekly job stored it (the briefs table, migration 005): one row per
// portal and one with no portal for the Top 10. Bodies are JSON written by Python; everything here
// reads them defensively, so an odd row shows as missing, never as an error. No imports, so
// `node --test` can load it directly.

export type BriefCall = {
  id: string;
  title: string;
  portal: string | null;
  url: string | null;
  verdict: string | null;
  deadline: string | null;
  daysLeft: number | null;
  reason: string;
  status: string | null;
  by: string | null;
};
export type PortalBrief = {
  portal: string;
  waiting: number;
  newTotal: number;
  newByVerdict: [string, number][];
  topPicks: BriefCall[];
  closingSoon: BriefCall[];
  decided: BriefCall[];
  health: string;
};
export type JudgeLine = { judge: string; decided: number; matches: number; misses: number; false_alarms: number };
export type TopBrief = { top: BriefCall[]; rankedBy: string; judges: JudgeLine[] };

/** The weekly summary's order for its verdict counts. */
const VERDICT_ORDER = ["yes", "maybe", "no", "not reviewed yet", "rejected by filter"];
const JUDGE_NAMES: Record<string, string> = { claude: "Claude", grok: "Grok" };
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

type Json = Record<string, unknown>;

function read(body: unknown): Json | null {
  if (typeof body !== "string") return null;
  try {
    const value: unknown = JSON.parse(body);
    return value && typeof value === "object" && !Array.isArray(value) ? (value as Json) : null;
  } catch {
    return null;
  }
}

const text = (v: unknown): string | null => (typeof v === "string" && v.trim() ? v : null);
const count = (v: unknown): number => (typeof v === "number" && Number.isFinite(v) ? v : 0);

function calls(v: unknown): BriefCall[] {
  if (!Array.isArray(v)) return [];
  const found: BriefCall[] = [];
  for (const item of v) {
    if (!item || typeof item !== "object") continue;
    const c = item as Json;
    const id = text(c.id);
    if (!id) continue;
    found.push({
      id,
      title: text(c.title) ?? id,
      portal: text(c.portal),
      url: text(c.url),
      verdict: text(c.verdict),
      deadline: text(c.deadline),
      daysLeft: typeof c.days_left === "number" ? c.days_left : null,
      reason: text(c.reason) ?? "",
      status: text(c.status),
      by: text(c.by),
    });
  }
  return found;
}

/** One portal's week, or null when the row has no portal name or is not JSON. */
export function parseBrief(body: unknown): PortalBrief | null {
  const b = read(body);
  const portal = b && text(b.portal);
  if (!b || !portal) return null;
  const fresh = (b.new && typeof b.new === "object" ? b.new : {}) as Json;
  const byVerdict = (fresh.by_verdict && typeof fresh.by_verdict === "object" ? fresh.by_verdict : {}) as Json;
  const known = VERDICT_ORDER.filter((v) => count(byVerdict[v]) > 0).map((v): [string, number] => [v, count(byVerdict[v])]);
  const others = Object.keys(byVerdict)
    .filter((v) => !VERDICT_ORDER.includes(v) && count(byVerdict[v]) > 0)
    .map((v): [string, number] => [v, count(byVerdict[v])]);
  return {
    portal,
    waiting: count(b.waiting),
    newTotal: count(fresh.total),
    newByVerdict: [...known, ...others],
    topPicks: calls(b.top_picks),
    closingSoon: calls(b.closing_soon),
    decided: calls(b.decided),
    health: text(b.health) ?? "",
  };
}

/** The Top 10 across portals, how it was ranked, and the judges' records that week; null when not JSON. */
export function parseTop(body: unknown): TopBrief | null {
  const b = read(body);
  if (!b) return null;
  const judges: JudgeLine[] = Array.isArray(b.judges)
    ? b.judges.flatMap((j) => {
        if (!j || typeof j !== "object") return [];
        const r = j as Json;
        const judge = text(r.judge);
        return judge
          ? [{ judge, decided: count(r.decided), matches: count(r.matches), misses: count(r.misses), false_alarms: count(r.false_alarms) }]
          : [];
      })
    : [];
  return { top: calls(b.top), rankedBy: text(b.ranked_by) ?? "", judges };
}

/** "week of 19 Oct", with the year when it is not `now`'s year; the raw text when it is not a date. */
export function weekLabel(week: string, now: Date = new Date()): string {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(week);
  if (!m) return week;
  const year = Number(m[1]);
  const label = `week of ${Number(m[3])} ${MONTHS.at(Number(m[2]) - 1) ?? m[2]}`;
  return year === now.getUTCFullYear() ? label : `${label} ${year}`;
}

/** The deadline as the portal wrote it, and the days left as the brief counted them. */
export function closesText(deadline: string | null, daysLeft: number | null): string {
  if (!deadline) return "no deadline";
  if (daysLeft === null) return deadline;
  const left = daysLeft === 0 ? "today" : daysLeft === 1 ? "1 day" : `${daysLeft} days`;
  return `${deadline} (${left})`;
}

function plural(n: number, one: string, many: string): string {
  return `${n} ${n === 1 ? one : many}`;
}

/** The judges line of the Monday Slack summary, or "" before any judge has a verdict that counts. */
export function judgesSentence(judges: JudgeLine[]): string {
  const parts = judges
    .filter((j) => j.decided > 0)
    .map((j) => `${JUDGE_NAMES[j.judge] ?? j.judge} matched ${j.matches} of ${j.decided} ` +
      `(${plural(j.misses, "miss", "misses")}, ${plural(j.false_alarms, "false alarm", "false alarms")})`);
  if (parts.length === 0) return "";
  return `Judges against your decisions, counting only verdicts given before you decided: ${parts.join("; ")}.`;
}

/** A portal's board label links to that portal's calls on All calls. */
export function boardHref(portal: string): string {
  return `/calls?${new URLSearchParams({ portal }).toString()}`;
}
