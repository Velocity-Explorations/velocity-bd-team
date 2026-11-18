import { test } from "node:test";
import assert from "node:assert/strict";
import { isProblem, isStale, pickRunsSort, portalScan, runHeadline } from "./runs.ts";

const NOW = new Date("2026-10-28T12:00:00Z");
const run = (status: string, started: string, finished: string | null = null) => ({ status, started_at: started, finished_at: finished });

test("a run still marked running two hours after it started has no finish recorded", () => {
  assert.equal(isStale(run("running", "2026-10-28T09:59:00Z"), NOW), true);
  assert.equal(isStale(run("running", "2026-10-28T11:00:00Z"), NOW), false);
  assert.equal(isStale(run("completed", "2026-10-28T09:00:00Z", "2026-10-28T09:05:00Z"), NOW), false);
});

test("Scan problems are runs that failed, timed out or never finished (PRO-573)", () => {
  assert.equal(isProblem(run("error", "2026-10-28T11:00:00Z", "2026-10-28T11:01:00Z"), NOW), true);
  assert.equal(isProblem(run("skipped_timeout", "2026-10-28T11:00:00Z", "2026-10-28T11:05:00Z"), NOW), true);
  assert.equal(isProblem(run("running", "2026-10-28T08:00:00Z"), NOW), true);
  assert.equal(isProblem(run("running", "2026-10-28T11:30:00Z"), NOW), false);
  assert.equal(isProblem(run("completed", "2026-10-28T11:00:00Z", "2026-10-28T11:01:00Z"), NOW), false);
});

test("each run's headline in words", () => {
  assert.equal(runHeadline(run("completed", "2026-10-28T11:00:00Z", "2026-10-28T11:01:00Z"), NOW), "Completed");
  assert.equal(runHeadline(run("skipped_timeout", "2026-10-28T11:00:00Z"), NOW), "Fetch timed out and was skipped");
  assert.equal(runHeadline(run("error", "2026-10-28T11:00:00Z"), NOW), "Failed");
  assert.equal(runHeadline(run("running", "2026-10-28T11:30:00Z"), NOW), "Running now");
  assert.equal(runHeadline(run("running", "2026-10-28T08:00:00Z"), NOW), "No finish recorded");
});

test("the Started column sorts newest first, or oldest first when asked", () => {
  assert.equal(pickRunsSort(undefined), "desc");
  assert.equal(pickRunsSort("asc"), "asc");
  assert.equal(pickRunsSort(["asc", "desc"]), "asc");
  assert.equal(pickRunsSort("sideways"), "desc");
});

// ------------------------------------------------------------------ the newest scan of each portal (Task 6, 18 Nov 2026)

const scan = (status: string, started: string, counts: string | null, finished: string | null = started) =>
  ({ portal: "P", status, started_at: started, finished_at: finished, stage_counts: counts });

test("a portal's newest scan gives its counts, and a scan that read something and finished needs nothing", () => {
  assert.deepEqual(portalScan(scan("completed", "2026-10-26T05:00:00Z", '{"fetched": 290, "filtered": 90, "reviewed": 75, "new": 15}'), NOW),
    { fetched: 290, filtered: 90, reviewed: 75, added: 15, flag: "", tone: "good" });
});

test("a failed, timed out or unfinished scan, one that found nothing, or no scan for over a week is flagged", () => {
  const counts = '{"fetched": 4, "filtered": 0, "reviewed": 0, "new": 0}';
  assert.deepEqual([portalScan(scan("error", "2026-10-26T05:00:00Z", null), NOW).flag, portalScan(scan("error", "2026-10-26T05:00:00Z", null), NOW).tone],
    ["failed", "bad"]);
  assert.equal(portalScan(scan("skipped_timeout", "2026-10-26T05:00:00Z", null), NOW).flag, "timed out");
  assert.equal(portalScan(scan("running", "2026-10-28T09:00:00Z", null, null), NOW).flag, "no finish recorded");
  assert.equal(portalScan(scan("running", "2026-10-28T11:30:00Z", null, null), NOW).flag, "running now");
  const nothing = portalScan(scan("completed", "2026-10-26T05:00:00Z", '{"fetched": 0, "filtered": 0, "reviewed": 0, "new": 0}'), NOW);
  assert.deepEqual([nothing.flag, nothing.tone, nothing.fetched], ["found nothing", "warn", 0]);
  assert.equal(portalScan(scan("completed", "2026-10-18T05:00:00Z", counts), NOW).flag, "no scan for 10 days");
  assert.equal(portalScan(scan("completed", "2026-10-26T05:00:00Z", "not json"), NOW).fetched, null);   // counts unreadable
});
