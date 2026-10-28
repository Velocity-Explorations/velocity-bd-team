import { test } from "node:test";
import assert from "node:assert/strict";
import { automationCards, callViewCards, pickCallView } from "./views.ts";

const PARAMS = {
  portal: ["SAM.gov", "NSTXL"],
  tag: "Software",
  state: "open",
  sort: "due",
  dir: "desc",
  verdict: "yes",
  judges: "agree",
  q: "space",
};

test("pickCallView knows the queue's views and falls back to Needs review", () => {
  assert.equal(pickCallView("due-soon"), "due-soon");
  assert.equal(pickCallView(["due-soon", "x"]), "due-soon");
  assert.equal(pickCallView("nope"), "needs-review");
  assert.equal(pickCallView(undefined), "needs-review");
});

test("switching cards keeps the portal, tag and open or closed filters, and drops the sort and column filters (N6)", () => {
  const cards = callViewCards({ current: "due-soon", params: PARAMS, counts: { "needs-review": 28, "due-soon": 2, all: 187 }, perPerson: true, dueBy: "11 Nov" });
  assert.deepEqual(
    cards.map((c) => c.href),
    [
      "/review?portal=SAM.gov&portal=NSTXL&tag=Software&state=open",
      "/review?view=due-soon&portal=SAM.gov&portal=NSTXL&tag=Software&state=open",
      "/calls?portal=SAM.gov&portal=NSTXL&tag=Software&state=open",
    ],
  );
  assert.deepEqual(cards.map((c) => c.current), [false, true, false]);
});

test("the calls cards say what each counts, the waiting count in the accent (VC1)", () => {
  const cards = callViewCards({ current: "all", params: {}, counts: { "needs-review": 28, "due-soon": 2, all: 187 }, perPerson: true, dueBy: "11 Nov" });
  assert.deepEqual(
    cards.map((c) => [c.label, c.count, c.description, c.needsYou]),
    [
      ["Needs review", 28, "every call waiting for you", true],
      ["Due soon", 2, "closing by 11 Nov", false],
      ["All calls", 187, "every call scanned, rejects too", false],
    ],
  );
  const shared = callViewCards({ current: "needs-review", params: {}, counts: { "needs-review": 5, "due-soon": 0, all: 9 }, perPerson: false, dueBy: "11 Nov" });
  assert.equal(shared[0].description, "every call nobody has decided");
});

test("the automation cards link its pages and mark the open one", () => {
  const cards = automationCards({ current: "runs", waiting: 2, kinds: "a keyword change, a scan", runs: 26, lastRun: "last completed 2026-10-24 08:07 MDT", agree: { both: 62, agree: 48 } });
  assert.deepEqual(
    cards.map((c) => [c.label, c.href, c.count, c.description, c.current, c.needsYou]),
    [
      ["Agent update requests", "/requests", 2, "a keyword change, a scan", false, true],
      ["Scans", "/runs", 26, "last completed 2026-10-24 08:07 MDT", true, false],
      ["Judges agree", "/judges", "77%", "48 of 62 calls", false, false],
    ],
  );
  const none = automationCards({ current: "judges", waiting: 0, kinds: "", runs: 0, lastRun: "", agree: null });
  assert.deepEqual(none.map((c) => [c.count, c.description]), [[0, "nothing waiting"], [0, "no scans yet"], ["none", "no call judged by both yet"]]);
});
