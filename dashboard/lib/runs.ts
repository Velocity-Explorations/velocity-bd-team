// Scans and Scan problems (PRO-573): which runs are problems, each run's headline, and the Started
// column's sort. No imports, so `node --test` can load it directly.

type RunTimes = { status: string; started_at: string; finished_at: string | null };

/** How long a run may stay "running" before it counts as having died. */
export const STALE_MS = 2 * 60 * 60 * 1000;

/** A run still marked running two hours after it started: the process probably died. */
export function isStale(run: RunTimes, now: Date): boolean {
  return run.status === "running" && !run.finished_at && now.getTime() - new Date(run.started_at).getTime() > STALE_MS;
}

/** Scan problems: runs that failed, timed out, or never recorded a finish. */
export function isProblem(run: RunTimes, now: Date): boolean {
  return run.status === "error" || run.status === "skipped_timeout" || isStale(run, now);
}

/** The most recent run's headline in words. */
export function runHeadline(run: RunTimes, now: Date): string {
  if (isStale(run, now)) return "No finish recorded";
  switch (run.status) {
    case "completed":
      return "Completed";
    case "skipped_timeout":
      return "Fetch timed out and was skipped";
    case "error":
      return "Failed";
    case "running":
      return "Running now";
    default:
      return run.status;
  }
}

/** The Started column: newest first unless the address asks for oldest first. */
export function pickRunsSort(raw: string | string[] | undefined): "asc" | "desc" {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value === "asc" ? "asc" : "desc";
}

/** A week and a day: the scan runs every Sunday night, so a portal not scanned for longer has missed one. */
const SCAN_GAP_DAYS = 8;

type PortalRun = RunTimes & { portal: string; stage_counts: string | null };

/**
 * A portal's newest scan in one line (Task 6, 18 Nov 2026): its counts, and what to look at. A failure, a timeout or a
 * run with no finish is bad; a scan running now, one that found nothing, or no scan for over a week is worth a look.
 * Nothing found is not always wrong (APFIT and Space Florida often have nothing open), so it is a look, not a failure.
 */
export function portalScan(run: PortalRun, now: Date): {
  fetched: number | null; filtered: number | null; reviewed: number | null; added: number | null; flag: string; tone: "good" | "warn" | "bad";
} {
  let counts: Record<string, unknown> = {};
  try {
    const parsed: unknown = JSON.parse(run.stage_counts ?? "{}");
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) counts = parsed as Record<string, unknown>;
  } catch {
    counts = {};
  }
  const num = (key: string): number | null => (typeof counts[key] === "number" ? (counts[key] as number) : null);
  const base = { fetched: num("fetched"), filtered: num("filtered"), reviewed: num("reviewed"), added: num("new") };
  const days = Math.floor((now.getTime() - new Date(run.started_at).getTime()) / (24 * 3600 * 1000));
  if (run.status === "error") return { ...base, flag: "failed", tone: "bad" };
  if (run.status === "skipped_timeout") return { ...base, flag: "timed out", tone: "bad" };
  if (isStale(run, now)) return { ...base, flag: "no finish recorded", tone: "bad" };
  if (run.status === "running") return { ...base, flag: "running now", tone: "warn" };
  if (base.fetched === 0) return { ...base, flag: "found nothing", tone: "warn" };
  if (days > SCAN_GAP_DAYS) return { ...base, flag: `no scan for ${days} days`, tone: "warn" };
  return { ...base, flag: "", tone: "good" };
}
