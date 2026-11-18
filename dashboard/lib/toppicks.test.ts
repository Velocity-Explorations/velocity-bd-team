import assert from "node:assert/strict";
import { test } from "node:test";
import { agreementOf, isPickRating, PICK_LABELS, picksFor, reviewWeeks, type PickRow } from "./toppicks.ts";

const ROWS: PickRow[] = [
  { week_of: "2026-11-16", call_id: "a", rated_by: "David Wood", rating: "good_pick", comment: "fits our C2 work", rated_at: "2026-11-18T10:00:00Z" },
  { week_of: "2026-11-16", call_id: "a", rated_by: "Shaun Jones", rating: "not_a_fit", comment: null, rated_at: "2026-11-18T11:00:00Z" },
  { week_of: "2026-11-16", call_id: "b", rated_by: "David Wood", rating: "good_pick", comment: null, rated_at: "2026-11-18T10:05:00Z" },
  { week_of: "2026-11-16", call_id: "b", rated_by: "Shaun Jones", rating: "good_pick", comment: "yes", rated_at: "2026-11-18T11:05:00Z" },
  { week_of: "2026-11-09", call_id: "b", rated_by: "Shaun Jones", rating: "not_a_fit", comment: "too broad", rated_at: "2026-11-10T09:00:00Z" },
];

test("a pick is rated Good pick, Not a fit or Unsure, and nothing else (Task 5, 18 Nov 2026)", () => {
  assert.deepEqual(Object.values(PICK_LABELS), ["Good pick", "Not a fit", "Unsure"]);
  assert.equal(isPickRating("good_pick"), true);
  assert.equal(isPickRating("unsure"), true);
  assert.equal(isPickRating("pursue"), false);
  assert.equal(isPickRating(undefined), false);
});

test("two or more ratings agree or split; one rating or none says so", () => {
  assert.equal(agreementOf(["good_pick", "good_pick"]), "agree");
  assert.equal(agreementOf(["good_pick", "not_a_fit"]), "split");
  assert.equal(agreementOf(["good_pick", "unsure"]), "split");
  assert.equal(agreementOf(["unsure"]), "one");
  assert.equal(agreementOf([]), "none");
});

test("each week's Top 10 lists every reviewer's rating and comment per pick, with whether they agree", () => {
  const weeks = reviewWeeks(
    [
      { week: "2026-11-16", picks: [{ id: "a", title: "A call", portal: "SAM.gov" }, { id: "b", title: "B call", portal: "DSIP" }, { id: "c", title: "C call", portal: null }] },
      { week: "2026-11-09", picks: [{ id: "b", title: "B call", portal: "DSIP" }] },
    ],
    ROWS,
  );
  assert.equal(weeks.length, 2);
  const [now, before] = weeks;
  assert.deepEqual(now.reviewers, ["David Wood", "Shaun Jones"]);
  assert.deepEqual(now.picks.map((p) => [p.place, p.id, p.agreement]), [[1, "a", "split"], [2, "b", "agree"], [3, "c", "none"]]);
  assert.deepEqual(now.picks[0].by["David Wood"], { rating: "good_pick", comment: "fits our C2 work" });
  assert.deepEqual(now.picks[0].by["Shaun Jones"], { rating: "not_a_fit", comment: null });
  assert.deepEqual(now.summary, { picks: 3, rated: 2, agree: 1, split: 1 });
  assert.deepEqual(before.reviewers, ["Shaun Jones"]);
  assert.deepEqual(before.picks[0].by["Shaun Jones"], { rating: "not_a_fit", comment: "too broad" });   // each week keeps its own
  assert.equal(before.picks[0].agreement, "one");
});

test("on Home the viewer sees their own rating of each pick and everyone else's", () => {
  const { mine, others } = picksFor(ROWS, "2026-11-16", "David Wood");
  assert.deepEqual(mine.get("a"), { rating: "good_pick", comment: "fits our C2 work" });
  assert.deepEqual(others.get("a"), [{ person: "Shaun Jones", rating: "not_a_fit", comment: null }]);
  assert.equal(mine.get("c"), undefined);
  assert.equal(picksFor(ROWS, "2026-11-16", null).mine.size, 0);
  assert.equal(picksFor(ROWS, "2026-11-16", null).others.get("b")?.length, 2);
});
