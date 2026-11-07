import assert from "node:assert/strict";
import { test } from "node:test";
import { parseSuggestion, suggestStatus, withSuggestedFirst } from "./suggest.ts";

const FORMATS = ["White paper", "RFI response", "Full proposal"];

test("a stored suggestion is read defensively, keeping only what the dialog offers", () => {
  const s = parseSuggestion(JSON.stringify({
    format: "White paper", format_why: "It asks for white papers.", approval_mode: "key_gates", approval_why: "Familiar.",
    direction: "Lead with PP-01.", builds_on: [{ id: "fold-a", why: "Closest bid." }, { id: "gone", why: "x" }, { id: 4 }],
  }), FORMATS, new Set(["fold-a", "fold-b"]));
  assert.deepEqual(s, {
    format: "White paper", formatWhy: "It asks for white papers.", approvalMode: "key_gates", approvalWhy: "Familiar.",
    direction: "Lead with PP-01.", buildsOn: [{ id: "fold-a", why: "Closest bid." }],
  });
  const odd = parseSuggestion('{"format":"Poem","approval_mode":"sometimes","builds_on":"no"}', FORMATS, new Set());
  assert.equal(odd?.format, null);
  assert.equal(odd?.approvalMode, null);
  assert.deepEqual(odd?.buildsOn, []);
  assert.equal(parseSuggestion("not json", FORMATS, new Set()), null);
  assert.equal(parseSuggestion(null, FORMATS, new Set()), null);
});

test("the suggested past work comes first, in Claude's order, and leaves its usual group", () => {
  const groups = [
    { title: "Past submissions", items: [{ id: "a", label: "A" }, { id: "b", label: "B" }, { id: "c", label: "C" }] },
    { title: "Company reference", items: [{ id: "r", label: "R" }] },
  ];
  assert.deepEqual(withSuggestedFirst(groups, ["r", "b", "missing"]), [
    { title: "Suggested by Claude", items: [{ id: "r", label: "R" }, { id: "b", label: "B" }] },
    { title: "Past submissions", items: [{ id: "a", label: "A" }, { id: "c", label: "C" }] },
  ]);
  assert.deepEqual(withSuggestedFirst(groups, []), groups);
});

test("the status says what the person waits on", () => {
  const now = Date.parse("2026-11-07T15:00:00Z");
  assert.equal(suggestStatus("queued", "2026-11-07T14:59:50Z", now), "Claude is reading the call and your past work, about half a minute");
  assert.equal(suggestStatus("working", "2026-11-07T14:59:50Z", now), "Claude is reading the call and your past work, about half a minute");
  assert.equal(suggestStatus("queued", "2026-11-07T14:40:00Z", now), "The assistant is offline, so the suggestion waits until it is back");
  assert.equal(suggestStatus("done", null, now), "");
});
