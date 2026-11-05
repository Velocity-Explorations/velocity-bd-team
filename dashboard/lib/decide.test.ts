import { test } from "node:test";
import assert from "node:assert/strict";
import { asksReason, decideLabel, dueLine, NOT_RELEVANT_REASONS, noteSource, readChoice, reasonNote, yourVote } from "./decide.ts";

const VOTES = [
  { person: "Shaun Jones", status: "pursue", decided_at: "2026-10-27T10:00:00Z" },
  { person: "David Wood", status: "dismissed", decided_at: "2026-10-27T11:00:00Z" },
];

test("your vote is your latest decision on the call, or none", () => {
  assert.deepEqual(yourVote(VOTES, "David Wood"), VOTES[1]);
  assert.equal(yourVote(VOTES, "Lisa"), null);
  assert.equal(yourVote(VOTES, null), null);
});

test("the Decide button reads Decide, Change or Add yours (Q14, C5)", () => {
  assert.equal(decideLabel({ yours: null, callStatus: null }), "Decide");
  assert.equal(decideLabel({ yours: VOTES[1], callStatus: "pursue" }), "Change");
  assert.equal(decideLabel({ yours: null, callStatus: "pursue" }), "Add yours");
});

test("a call you have not decided that closes within 14 days says when", () => {
  assert.equal(dueLine(0), "due today");
  assert.equal(dueLine(1), "due tomorrow");
  assert.equal(dueLine(3), "due in 3 days");
  assert.equal(dueLine(14), "due in 14 days");
  assert.equal(dueLine(15), "");
  assert.equal(dueLine(-1), "");
  assert.equal(dueLine(null), "");
});

test("a note came from a Slack thread reply when its author is a Slack member id", () => {
  assert.equal(noteSource("U08V7ULPH1N"), "Slack thread reply");
  assert.equal(noteSource("David Wood"), "on the dashboard");
  assert.equal(noteSource(null), "on the dashboard");
});


test("Not relevant asks why when Claude rated the call yes or maybe (David, 5 Nov)", () => {
  assert.equal(asksReason("yes"), true);
  assert.equal(asksReason("maybe"), true);
  assert.equal(asksReason("no"), false);
  assert.equal(asksReason(null), false);
});

test("the reasons offered are five quick picks", () => {
  assert.deepEqual(NOT_RELEVANT_REASONS.map((r) => r.label), [
    "Mostly hardware", "Staffing or IT support", "Wrong customer or eligibility", "Too broad, no clear fit", "Award or sole-source notice",
  ]);
});

test("a Decide button's value carries the decision and, for Not relevant, its reason", () => {
  assert.deepEqual(readChoice("pursue"), { status: "pursue", reason: null });
  assert.deepEqual(readChoice("pursue_draft"), { status: "pursue_draft", reason: null });
  assert.deepEqual(readChoice("not_relevant:hardware"), { status: "not_relevant", reason: "hardware" });
  assert.deepEqual(readChoice("not_relevant:other"), { status: "not_relevant", reason: "other" });
  assert.deepEqual(readChoice("not_relevant:nonsense"), { status: "not_relevant", reason: null });
  assert.deepEqual(readChoice(null), { status: null, reason: null });
});

test("the reason becomes the decision's note, with the person's own words after it", () => {
  assert.equal(reasonNote("hardware", ""), "Mostly hardware");
  assert.equal(reasonNote("hardware", " the software is a small part of a radar upgrade "), "Mostly hardware: the software is a small part of a radar upgrade");
  assert.equal(reasonNote("other", "Only open to universities"), "Only open to universities");
  assert.equal(reasonNote("other", "  "), "");
  assert.equal(reasonNote(null, "a note"), "a note");
});
