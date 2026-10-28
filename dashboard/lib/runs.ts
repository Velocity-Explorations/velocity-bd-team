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
