import { test } from "node:test";
import assert from "node:assert/strict";
import { formatAgo, formatDue, formatDuration, formatTime, isoNow, localInput, parseStageCounts, zonedToIso } from "./format.ts";

test("isoNow matches the ledger format: second precision, Z suffix", () => {
  assert.equal(isoNow(new Date("2026-10-17T09:44:33.789Z")), "2026-10-17T09:44:33Z");
});

test("formatTime renders in the configured zone with its abbreviation", () => {
  assert.equal(formatTime("2026-10-16T11:35:06Z", "America/Denver"), "2026-10-16 05:35 MDT");
  assert.equal(formatTime("2026-12-01T12:00:00Z", "America/Denver"), "2026-12-01 05:00 MST");
  assert.equal(formatTime("2026-10-16T11:35:06Z", "UTC"), "2026-10-16 11:35 UTC");
});

test("formatTime returns an empty string for missing or invalid input", () => {
  assert.equal(formatTime(null, "UTC"), "");
  assert.equal(formatTime(undefined, "UTC"), "");
  assert.equal(formatTime("not a date", "UTC"), "");
});

test("formatDuration", () => {
  assert.equal(formatDuration("2026-10-16T11:35:06Z", "2026-10-16T11:37:55Z"), "2m 49s");
  assert.equal(formatDuration("2026-10-16T11:35:06Z", "2026-10-16T11:35:51Z"), "45s");
  assert.equal(formatDuration("2026-10-16T10:00:00Z", "2026-10-16T11:02:05Z"), "1h 02m");
  assert.equal(formatDuration("2026-10-16T11:35:06Z", null), "");
});

test("formatAgo", () => {
  const now = new Date("2026-10-17T12:00:00Z");
  assert.equal(formatAgo("2026-10-17T11:59:30Z", now), "just now");
  assert.equal(formatAgo("2026-10-17T11:48:00Z", now), "12 min ago");
  assert.equal(formatAgo("2026-10-17T09:00:00Z", now), "3 h ago");
  assert.equal(formatAgo("2026-10-15T12:00:00Z", now), "2 d ago");
  assert.equal(formatAgo(null, now), "");
});

test("parseStageCounts keeps numeric entries in order and tolerates junk", () => {
  assert.deepEqual(parseStageCounts('{"fetched": 60, "filtered": 0, "reviewed": 3, "new": 1}'), [
    ["fetched", 60],
    ["filtered", 0],
    ["reviewed", 3],
    ["new", 1],
  ]);
  assert.deepEqual(parseStageCounts('{"found": 60, "note": "x"}'), [["found", 60]]);
  assert.deepEqual(parseStageCounts(null), []);
  assert.deepEqual(parseStageCounts("garbage"), []);
  assert.deepEqual(parseStageCounts("[1, 2]"), []);
});

test("formatDue shows ISO deadlines in the dashboard's zone and leaves portal text alone", () => {
  assert.equal(formatDue("2026-11-05T17:00:00-05:00", "America/Denver"), "2026-11-05 15:00 MST");
  assert.equal(formatDue("2026-10-28T23:59:59-04:00", "America/Denver"), "2026-10-28 21:59 MDT");
  assert.equal(formatDue("2026-10-30", "America/Denver"), "2026-10-30");
  assert.equal(formatDue("30 OCT 2026 : 21:59 MDT", "America/Denver"), "30 OCT 2026 : 21:59 MDT");
  assert.equal(formatDue(null, "UTC"), "");
});


test("a time typed in the viewer's zone is kept in UTC, winter and summer alike", () => {
  assert.equal(zonedToIso("2026-11-24T15:40", "America/Denver"), "2026-11-24T22:40:00Z");
  assert.equal(zonedToIso("2026-07-01T09:00", "America/Denver"), "2026-07-01T15:00:00Z");
  assert.equal(zonedToIso("2026-07-01T09:00", "UTC"), "2026-07-01T09:00:00Z");
  for (const bad of ["", "tomorrow", "2026-13-01T09:00", "2026-07-01"]) assert.equal(zonedToIso(bad, "UTC"), null, bad);
});

test("a stored time reads back as the zone's wall time for a datetime field", () => {
  assert.equal(localInput("2026-11-24T22:40:00Z", "America/Denver"), "2026-11-24T15:40");
  assert.equal(localInput(null, "UTC"), "");
});
