import { test } from "node:test";
import assert from "node:assert/strict";
import { DECISIONS, HUMAN_STATUSES, isDecision, pickAllowed, planDecision } from "./values.ts";

test("decisions are exactly the ledger's human_status values", () => {
  assert.deepEqual(DECISIONS.map((d) => d.value), ["pursue", "not_relevant", "submitted", "dismissed"]);
  assert.deepEqual([...HUMAN_STATUSES], ["pursue", "not_relevant", "submitted", "dismissed"]);
  assert.equal(isDecision("not_relevant"), true);
  assert.equal(isDecision("maybe"), false);
  assert.equal(isDecision(undefined), false);
});

test("pickAllowed keeps a filter value only when it is allowed", () => {
  const allowed = ["yes", "maybe"] as const;
  assert.equal(pickAllowed("maybe", allowed), "maybe");
  assert.equal(pickAllowed("no", allowed), "");
  assert.equal(pickAllowed(["yes", "maybe"], allowed), "yes");
  assert.equal(pickAllowed(undefined, allowed), "");
});

test("planDecision: a different status decides, the same status with a note only adds the note", () => {
  assert.equal(planDecision(null, "pursue", ""), "decide");
  assert.equal(planDecision("pursue", "submitted", ""), "decide");
  assert.equal(planDecision("pursue", "pursue", "called the PM"), "note");
  assert.equal(planDecision("pursue", "pursue", "   "), "noop");
});
