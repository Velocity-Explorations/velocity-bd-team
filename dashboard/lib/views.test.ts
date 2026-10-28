import { test } from "node:test";
import assert from "node:assert/strict";
import { automationCards, callViewCards, pickCallView, pressedCard, viewJudges, type CallCard } from "./views.ts";

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
const COUNTS: Record<CallCard, number> = {
  "needs-review": 28, top10: 10, "due-soon": 2, "judges-agree": 19, "judges-disagree": 9, new: 28, all: 187,
};

function cards(current: CallCard | null, perPerson = true) {
  return callViewCards({
    current, params: PARAMS, counts: COUNTS, perPerson, dueBy: "8 Nov", newSince: "19 Oct", briefWeek: "week of 19 Oct",
    agree: { both: 62, agree: 48 },
  });
}

test("pickCallView knows the queue's six views and falls back to Needs review", () => {
  for (const view of ["top10", "due-soon", "judges-agree", "judges-disagree", "new"]) assert.equal(pickCallView(view), view);
  assert.equal(pickCallView(["due-soon", "x"]), "due-soon");
  assert.equal(pickCallView("all"), "needs-review");
  assert.equal(pickCallView(undefined), "needs-review");
});

test("Calls has seven cards in order, each keeping the bar's filters and dropping the sort and column filters (N6)", () => {
  const row = cards("due-soon");
  const kept = "portal=SAM.gov&portal=NSTXL&tag=Software&state=open";
  assert.deepEqual(
    row.map((c) => [c.label, c.href]),
    [
      ["Needs review", `/review?${kept}`],
      ["Top 10", `/review?view=top10&${kept}`],
      ["Due soon", `/review?view=due-soon&${kept}`],
      ["Judges agree", `/review?view=judges-agree&${kept}`],
      ["Judges disagree", `/review?view=judges-disagree&${kept}`],
      ["New this week", `/review?view=new&${kept}`],
      ["All calls", `/calls?${kept}`],
    ],
  );
  assert.deepEqual(row.map((c) => c.current), [false, false, true, false, false, false, false]);
  assert.deepEqual(row.map((c) => c.needsYou), [true, false, false, false, false, false, false]);
  assert.ok(cards(null).every((c) => !c.current));
});

test("each card says what it counts (VC1)", () => {
  assert.deepEqual(
    cards("all").map((c) => [c.count, c.description]),
    [
      [28, "every call waiting for you"],
      [10, "Monday brief, week of 19 Oct, decided or not"],
      [2, "closing by 8 Nov"],
      [19, "same verdict; 77% of all calls, 48 of 62"],
      [9, "yes vs no listed first"],
      [28, "first seen since 19 Oct"],
      [187, "every call scanned, rejects too"],
    ],
  );
  const shared = callViewCards({ current: "needs-review", params: {}, counts: COUNTS, perPerson: false, dueBy: "8 Nov", newSince: "19 Oct", briefWeek: null, agree: null });
  assert.deepEqual([shared[0].description, shared[1].description, shared[3].description], ["nobody has decided these", "the live ranking, until the first brief", "same verdict"]);
});

test("the judges views set the judges filter themselves", () => {
  assert.equal(viewJudges("judges-agree", ""), "agree");
  assert.equal(viewJudges("judges-disagree", "agree"), "disagree");
  assert.equal(viewJudges("needs-review", "disagree"), "disagree");
  assert.equal(viewJudges("new", ""), "");
});

test("a column filter that matches no view leaves no card pressed (VC4)", () => {
  const none = { judges: "", verdict: "", tier: "" };
  assert.equal(pressedCard("due-soon", none), "due-soon");
  assert.equal(pressedCard("needs-review", { ...none, judges: "agree" }), "judges-agree");
  assert.equal(pressedCard("needs-review", { ...none, judges: "disagree" }), "judges-disagree");
  assert.equal(pressedCard("judges-agree", { ...none, judges: "agree" }), "judges-agree");
  assert.equal(pressedCard("needs-review", { ...none, verdict: "yes" }), null);
  assert.equal(pressedCard("new", { ...none, judges: "agree" }), null);
  assert.equal(pressedCard("judges-disagree", { ...none, tier: "tight" }), null);
});

test("Automation has five cards, each linking its view and marking the open one (PRO-573)", () => {
  const row = automationCards({
    current: "problems", waiting: 2, kinds: "a keyword change, a scan", decided: 3, runs: 26,
    lastRun: "last completed 2026-10-24 08:07 MDT", problems: 4, agree: { both: 62, agree: 48 },
  });
  assert.deepEqual(
    row.map((c) => [c.label, c.href, c.count, c.description, c.current, c.needsYou]),
    [
      ["Agent update requests", "/requests", 2, "a keyword change, a scan", false, true],
      ["Decided requests", "/requests?view=decided", 3, "the last 50, with their result", false, false],
      ["Scans", "/runs", 26, "last completed 2026-10-24 08:07 MDT", false, false],
      ["Scan problems", "/runs?view=problems", 4, "timeouts and errors", true, false],
      ["Judges agree", "/judges", "77%", "48 of 62 calls", false, false],
    ],
  );
  const none = automationCards({ current: "judges", waiting: 0, kinds: "", decided: 0, runs: 0, lastRun: "", problems: 0, agree: null });
  assert.deepEqual(
    none.map((c) => [c.count, c.description]),
    [[0, "nothing waiting"], [0, "none decided yet"], [0, "no scans yet"], [0, "no timeouts or errors"], ["none", "no call judged by both yet"]],
  );
});
