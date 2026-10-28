import { test } from "node:test";
import assert from "node:assert/strict";
import { isProblem, isStale, pickRunsSort, runHeadline } from "./runs.ts";

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
