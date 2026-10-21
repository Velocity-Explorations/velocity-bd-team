import { test } from "node:test";
import assert from "node:assert/strict";
import { DECISIONS, HUMAN_STATUSES, isDecision, pickAllowed, pickQueueMode, planDecision } from "./values.ts";

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
  assert.equal(planDecision(null, "pursue", "", null), "decide");
  assert.equal(planDecision("pursue", "submitted", "", "pursue"), "decide");
  assert.equal(planDecision("pursue", "pursue", "called the PM", "pursue"), "note");
  assert.equal(planDecision("pursue", "pursue", "   ", "pursue"), "noop");
});

test("planDecision: choosing the current decision when it is someone else's records yours", () => {
  assert.equal(planDecision("pursue", "pursue", "", null), "add");
  assert.equal(planDecision("pursue", "pursue", "worth a call", "dismissed"), "add");
  assert.equal(planDecision("pursue", "dismissed", "", null), "decide");
});

test("planDecision: from the queue while everyone decides, a different decision is kept beside the call's", () => {
  assert.equal(planDecision("pursue", "dismissed", "", null, true), "add");
  assert.equal(planDecision(null, "dismissed", "", null, true), "decide");
  assert.equal(planDecision("pursue", "dismissed", "", "dismissed", true), "noop");
  assert.equal(planDecision("pursue", "dismissed", "why not", "dismissed", true), "note");
});

test("pickQueueMode: everyone decides every call unless the queue is set to shared", () => {
  assert.equal(pickQueueMode(undefined), "each");
  assert.equal(pickQueueMode(" Shared "), "shared");
  assert.equal(pickQueueMode("anything else"), "each");
});
