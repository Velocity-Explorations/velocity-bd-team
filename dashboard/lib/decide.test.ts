import { test } from "node:test";
import assert from "node:assert/strict";
import { decideLabel, dueLine, noteSource, yourVote } from "./decide.ts";

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
