import { test } from "node:test";
import assert from "node:assert/strict";
import { COLUMNS, hiddenFromForm, readHidden } from "./columns.ts";

test("the tables' columns follow the handoff's order, with the details, tags and note box as choices (S1)", () => {
  assert.deepEqual(
    COLUMNS.queue.map((c) => c.key),
    ["call", "details", "tags", "votes", "description", "reason", "due", "seen", "note", "decide"],
  );
  assert.deepEqual(
    COLUMNS.calls.map((c) => c.key),
    ["call", "details", "tags", "filter", "votes", "description", "reason", "notes", "due", "seen", "decide"],
  );
});

test("with no saved choice both tables hide First seen, and All calls its Notes column (S4)", () => {
  for (const cookie of [undefined, "{oops", "[1, 2]"]) assert.deepEqual(readHidden(cookie), { queue: ["seen"], calls: ["notes", "seen"] });
});

test("a saved choice keeps only columns that exist and may be hidden; a page left out keeps its defaults", () => {
  assert.deepEqual(readHidden(JSON.stringify({ queue: ["reason", "call", "tier", "bogus"] })), { queue: ["reason"], calls: ["notes", "seen"] });
  assert.deepEqual(readHidden(JSON.stringify({ queue: [], calls: ["notes", "decide"] })), { queue: [], calls: ["notes"] });
});

test("the form hides every column whose box is unticked, but never Call or Decide (S2)", () => {
  const ticked = new Set(["show:queue:details", "show:queue:tags", "show:queue:votes", "show:queue:description", "show:queue:due",
                          "show:queue:note", "show:calls:tags", "show:calls:filter", "show:calls:votes", "show:calls:due", "show:calls:seen"]);
  assert.deepEqual(hiddenFromForm(ticked), { queue: ["reason", "seen"], calls: ["details", "description", "reason", "notes"] });
  assert.deepEqual(COLUMNS.queue.filter((c) => c.fixed).map((c) => c.key), ["call", "decide"]);
  assert.deepEqual(COLUMNS.calls.filter((c) => c.fixed).map((c) => c.key), ["call", "decide"]);
});

test("tags under the title are a choice in Table settings, shown by default (S3)", () => {
  assert.ok(COLUMNS.queue.some((c) => c.key === "tags" && !c.fixed));
  assert.ok(COLUMNS.calls.some((c) => c.key === "tags" && !c.fixed));
  assert.ok(!readHidden(undefined).queue.includes("tags"));
});
