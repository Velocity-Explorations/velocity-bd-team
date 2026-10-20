import { test } from "node:test";
import assert from "node:assert/strict";
import { judgedMisses, peopleAgreement, peopleSplit, personRecords, votesByCall, type DecisionRow, type JudgmentRow } from "./scoreboard.ts";

const name = (by: string) => (by === "U08V7ULPH1N" ? "David Wood" : by);

const judgments: JudgmentRow[] = [
  { call_id: "a", judge: "claude", verdict: "yes", rated_at: "2026-10-16T10:00:00Z" },
  { call_id: "a", judge: "grok", verdict: "no", rated_at: "2026-10-16T10:00:00Z" },
  { call_id: "b", judge: "claude", verdict: "yes", rated_at: "2026-10-16T10:00:00Z" },
  { call_id: "b", judge: "grok", verdict: "no", rated_at: "2026-10-20T10:00:00Z" },
];
const decisions: DecisionRow[] = [
  { call_id: "a", decided_by: "U08V7ULPH1N", status: "pursue", decided_at: "2026-10-17T10:00:00Z" },
  { call_id: "a", decided_by: "Shaun Jones", status: "submitted", decided_at: "2026-10-18T10:00:00Z" },
  { call_id: "b", decided_by: "Shaun Jones", status: "pursue", decided_at: "2026-10-17T09:00:00Z" },
  { call_id: "b", decided_by: "Shaun Jones", status: "dismissed", decided_at: "2026-10-17T12:00:00Z" },
  { call_id: "b", decided_by: "David Wood", status: "not_relevant", decided_at: "2026-10-18T12:00:00Z" },
];

test("personRecords scores each person's latest decision per call against verdicts given before it", () => {
  const records = Object.fromEntries(personRecords(decisions, judgments, ["claude", "grok"], name).map((r) => [r.person, r]));
  assert.equal(records["David Wood"].decided, 2);
  assert.deepEqual(records["David Wood"].withJudge.claude, { judged: 2, matches: 1 });
  assert.deepEqual(records["David Wood"].withJudge.grok, { judged: 1, matches: 0 });
  assert.equal(records["Shaun Jones"].decided, 2);
  assert.deepEqual(records["Shaun Jones"].withJudge.claude, { judged: 2, matches: 1 });
});

test("peopleAgreement compares people on the calls they both decided, treating submitted as pursue", () => {
  assert.deepEqual(peopleAgreement(decisions, name), [{ a: "David Wood", b: "Shaun Jones", shared: 2, agree: 2 }]);
});

test("judgedMisses lists calls the team pursued that a judge had called no", () => {
  const calls = [
    { id: "a", title: "Agentic C2", url: "https://x/a", status: "submitted", decided_at: "2026-10-18T10:00:00Z" },
    { id: "b", title: "Threat intel", url: null, status: "not_relevant", decided_at: "2026-10-18T12:00:00Z" },
  ];
  assert.deepEqual(judgedMisses(calls, judgments, ["claude", "grok"]), [{ id: "a", title: "Agentic C2", url: "https://x/a", judge: "grok" }]);
});

test("personRecords ignores a verdict given after anyone decided the call", () => {
  // Grok judged b after Shaun's first decision on it, so the decision may have been among its examples.
  const late: JudgmentRow[] = [...judgments, { call_id: "b", judge: "grok", verdict: "no", rated_at: "2026-10-17T10:00:00Z" }];
  const records = Object.fromEntries(personRecords(decisions, late, ["claude", "grok"], name).map((r) => [r.person, r]));
  assert.deepEqual(records["David Wood"].withJudge.grok, { judged: 1, matches: 0 });
});

test("votesByCall keeps each person's latest decision, oldest first, and peopleSplit spots a yes against a no", () => {
  const votes = votesByCall(decisions, name);
  assert.deepEqual(votes.get("b"), [
    { person: "Shaun Jones", status: "dismissed", decided_at: "2026-10-17T12:00:00Z" },
    { person: "David Wood", status: "not_relevant", decided_at: "2026-10-18T12:00:00Z" },
  ]);
  assert.equal(peopleSplit(votes.get("b") ?? []), false);
  assert.equal(peopleSplit([
    { person: "A", status: "pursue", decided_at: "t1" },
    { person: "B", status: "dismissed", decided_at: "t2" },
  ]), true);
});
