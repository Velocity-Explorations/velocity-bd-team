import { test } from "node:test";
import assert from "node:assert/strict";
import { closesText, judgesSentence, parseBrief, parseTop, weekLabel } from "./brief.ts";

const portalBody = JSON.stringify({
  portal: "Vulcan SOF",
  days: 7,
  waiting: 13,
  new: { total: 3, by_verdict: { maybe: 2, yes: 1 }, calls: [] },
  top_picks: [
    { id: "v-1", title: "IT & Cyber", portal: "Vulcan SOF", url: "https://portal.invalid/1", verdict: "yes",
      deadline: "27 OCT 2026 : 21:59 MDT", days_left: 7, reason: "Builds C2 software." },
    { title: "no id, so dropped" },
  ],
  closing_soon: [{ id: "v-2", title: "Picked call", url: null, deadline: "22 OCT 2026 : 10:00 MDT", days_left: 2, status: "pursue" }],
  decided: [{ id: "v-3", title: "Old call", url: null, status: "dismissed", by: "U08V7ULPH1N", at: "2026-10-16T18:00:00Z" }],
  health: "Vulcan SOF: the last scan completed at 19 Oct 06:03.",
});

test("parseBrief reads a portal's week, in the summary's verdict order, dropping calls without an id", () => {
  const brief = parseBrief(portalBody);
  assert.ok(brief);
  assert.equal(brief.portal, "Vulcan SOF");
  assert.equal(brief.waiting, 13);
  assert.equal(brief.newTotal, 3);
  assert.deepEqual(brief.newByVerdict, [["yes", 1], ["maybe", 2]]);
  assert.deepEqual(brief.topPicks.map((c) => c.id), ["v-1"]);
  assert.equal(brief.topPicks[0].reason, "Builds C2 software.");
  assert.equal(brief.closingSoon[0].status, "pursue");
  assert.equal(brief.decided[0].by, "U08V7ULPH1N");
  assert.equal(brief.health, "Vulcan SOF: the last scan completed at 19 Oct 06:03.");
});

test("parseBrief and parseTop never throw on an odd row", () => {
  assert.equal(parseBrief("not json"), null);
  assert.equal(parseBrief(null), null);
  assert.equal(parseBrief(JSON.stringify({ waiting: 2 })), null);   // no portal name
  const sparse = parseBrief(JSON.stringify({ portal: "SSC Front Door" }));
  assert.deepEqual(sparse && [sparse.waiting, sparse.newTotal, sparse.topPicks.length, sparse.health], [0, 0, 0, ""]);
  assert.equal(parseTop("[]"), null);
  assert.deepEqual(parseTop(JSON.stringify({ top: "nope" }))?.top, []);
});

test("parseTop reads the Top 10 with its ranking and the judges' records", () => {
  const top = parseTop(JSON.stringify({
    top: [{ id: "f-1", title: "Space Industry Days", portal: "SSC Front Door", url: null, verdict: "maybe", deadline: null,
            days_left: null, reason: "Topic fits." }],
    ranked_by: "yes before maybe, then the nearest deadline, then the newest",
    judges: [{ judge: "claude", decided: 3, matches: 2, misses: 0, false_alarms: 1 }],
  }));
  assert.ok(top);
  assert.deepEqual(top.top.map((c) => [c.id, c.portal, c.verdict]), [["f-1", "SSC Front Door", "maybe"]]);
  assert.equal(top.rankedBy, "yes before maybe, then the nearest deadline, then the newest");
  assert.equal(top.judges[0].matches, 2);
});

test("weekLabel names the Monday, with the year only when it is not this year", () => {
  const now = new Date("2026-10-21T12:00:00Z");
  assert.equal(weekLabel("2026-10-19", now), "week of 19 Oct");
  assert.equal(weekLabel("2025-12-29", now), "week of 29 Dec 2025");
  assert.equal(weekLabel("garbage", now), "garbage");
});

test("closesText gives the deadline as the portal wrote it and the days left", () => {
  assert.equal(closesText("27 OCT 2026 : 21:59 MDT", 7), "27 OCT 2026 : 21:59 MDT (7 days)");
  assert.equal(closesText("22 OCT 2026 : 10:00 MDT", 1), "22 OCT 2026 : 10:00 MDT (1 day)");
  assert.equal(closesText("21 OCT 2026 : 18:00 EDT", 0), "21 OCT 2026 : 18:00 EDT (today)");
  assert.equal(closesText(null, null), "no deadline");
});

test("judgesSentence reads like the Slack summary's line", () => {
  assert.equal(
    judgesSentence([
      { judge: "claude", decided: 3, matches: 2, misses: 0, false_alarms: 1 },
      { judge: "grok", decided: 1, matches: 0, misses: 1, false_alarms: 0 },
      { judge: "grok", decided: 0, matches: 0, misses: 0, false_alarms: 0 },
    ]),
    "Judges against your decisions, counting only verdicts given before you decided: Claude matched 2 of 3 (0 misses, 1 false alarm); Grok matched 0 of 1 (1 miss, 0 false alarms).",
  );
  assert.equal(judgesSentence([]), "");
});
