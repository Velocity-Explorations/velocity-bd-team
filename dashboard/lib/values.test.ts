import { test } from "node:test";
import assert from "node:assert/strict";
import { DECISIONS, HUMAN_STATUSES, isDecision, isVote, keepsCallDecision, pickAllowed, pickQueueMode, planDecision, STATUS_LABELS, unsurePlan } from "./values.ts";

test("the Decide menu offers the call's four decisions and Unsure, which is a vote only (David, 16 Nov 2026)", () => {
  assert.deepEqual(DECISIONS.map((d) => d.value), ["pursue", "not_relevant", "unsure", "submitted", "dismissed"]);
  assert.deepEqual(DECISIONS.map((d) => d.label), ["Pursue", "Not relevant", "Unsure", "Submitted", "Dismiss"]);
  assert.equal(STATUS_LABELS.unsure, "Unsure");
  assert.deepEqual([...HUMAN_STATUSES], ["pursue", "not_relevant", "submitted", "dismissed"]);
  assert.equal(isDecision("unsure"), false);   // a call's own decision never takes it
  assert.equal(isVote("unsure"), true);
  assert.equal(isVote("pursue"), true);
  assert.equal(isVote("maybe"), false);
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

test("a decision from the review queue leaves someone else's decision on the call, never the person's own", () => {
  // David, 16 Nov 2026: Pursue then Not relevant on Home's Top 10 left E-ICAM, JVCC and ERIS at Pursue.
  assert.equal(keepsCallDecision(true, true, "David Wood", ["David Wood", "David"]), false);
  assert.equal(keepsCallDecision(true, true, "David", ["David Wood", "David"]), false);
  assert.equal(keepsCallDecision(true, true, "Shaun", ["David Wood"]), true);
  assert.equal(keepsCallDecision(true, true, null, ["David Wood"]), true);
  assert.equal(keepsCallDecision(false, true, "Shaun", ["David Wood"]), false);
  assert.equal(keepsCallDecision(true, false, "Shaun", ["David Wood"]), false);   // no decisions table: nowhere to keep a vote
});

test("Unsure clears the call's decision only when it was the person's own, and otherwise adds their vote", () => {
  assert.equal(unsurePlan({ mine: null, note: "", own: false }), "add");
  assert.equal(unsurePlan({ mine: "pursue", note: "", own: false }), "add");
  assert.equal(unsurePlan({ mine: "pursue", note: "", own: true }), "clear");   // David pursued, now unsure: the call waits again
  assert.equal(unsurePlan({ mine: "unsure", note: "", own: false }), "noop");
  assert.equal(unsurePlan({ mine: "unsure", note: "who owns the data?", own: false }), "note");
});
