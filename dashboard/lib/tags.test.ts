import { test } from "node:test";
import assert from "node:assert/strict";
import { optionGroups, tagsByCall, withoutTags, type TagRow } from "./tags.ts";

const ROWS: TagRow[] = [
  { call_id: "a", tag: "OTA", source: "rule", tag_group: "type", position: 3 },
  { call_id: "a", tag: "SOCOM", source: "rule", tag_group: "customer", position: 28 },
  { call_id: "a", tag: "White paper", source: "claude", tag_group: "type", position: 0 },
  { call_id: "a", tag: "Software", source: "claude", tag_group: "work", position: 10 },
  { call_id: "a", tag: "Legacy", source: "claude", tag_group: null, position: null },
  { call_id: "a", tag: "Demo or exercise", source: "grok", tag_group: "type", position: 6 },
  { call_id: "a", tag: "Software", source: "grok", tag_group: "work", position: 10 },
  { call_id: "b", tag: "RFI", source: "claude", tag_group: "type", position: 2 },
  { call_id: "b", tag: "RFI", source: "grok", tag_group: "type", position: 2 },
];

test("a call shows one type first, then its other tags in the list's order, each saying who set it", () => {
  const shown = tagsByCall(ROWS);
  assert.deepEqual(shown.get("a"), [
    { text: "OTA", tone: "info", title: "Type, set by the call's data. Claude picked White paper. Grok picked Demo or exercise." },
    { text: "Software", tone: "grey", title: "Set by Claude and Grok" },
    { text: "SOCOM", tone: "grey", title: "Set by the call's data" },
    { text: "Legacy", tone: "grey", title: "Set by Claude" },   // no longer on the list: last
  ]);
  assert.deepEqual(shown.get("b"), [{ text: "RFI", tone: "info", title: "Type, set by Claude and Grok." }]);
  assert.equal(shown.get("c"), undefined);
});

test("without the call's data, Claude's type shows and Grok's other pick is named", () => {
  const shown = tagsByCall([
    { call_id: "c", tag: "Proposal", source: "grok", tag_group: "type", position: 1 },
    { call_id: "c", tag: "OTA", source: "claude", tag_group: "type", position: 3 },
  ]);
  assert.deepEqual(shown.get("c"), [{ text: "OTA", tone: "info", title: "Type, set by Claude. Grok picked Proposal." }]);
});

test("the Tag filter groups the list by type, work, customer and access", () => {
  const groups = optionGroups([
    { name: "Members only", tag_group: "access", covers: null },
    { name: "OTA", tag_group: "type", covers: "other transactions" },
    { name: "Software", tag_group: "work", covers: null },
  ]);
  assert.deepEqual(groups, [
    { label: "Type", names: ["OTA"] },
    { label: "Work", names: ["Software"] },
    { label: "Access", names: ["Members only"] },
  ]);
});

test("a detail that repeats a shown tag is dropped", () => {
  const details = [{ text: "OTA opportunity" }, { text: "members only", tone: "warn" as const }];
  assert.deepEqual(withoutTags(details, [{ text: "Members only", tone: "grey", title: "" }]), [{ text: "OTA opportunity" }]);
  assert.deepEqual(withoutTags(details, []), details);
});
