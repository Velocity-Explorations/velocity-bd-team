import { test } from "node:test";
import assert from "node:assert/strict";
import { COLUMNS, hiddenFromForm, readHidden } from "./columns.ts";

test("with no saved choice the queue hides Tier and All calls hides nothing", () => {
  assert.deepEqual(readHidden(undefined), { queue: ["tier"], calls: [] });
  assert.deepEqual(readHidden("{oops"), { queue: ["tier"], calls: [] });
  assert.deepEqual(readHidden("[1, 2]"), { queue: ["tier"], calls: [] });
});

test("a saved choice keeps only columns that exist and may be hidden; a page left out keeps its defaults", () => {
  assert.deepEqual(readHidden(JSON.stringify({ queue: ["reason", "call", "bogus"] })), { queue: ["reason"], calls: [] });
  assert.deepEqual(readHidden(JSON.stringify({ queue: [], calls: ["notes", "decision"] })), { queue: [], calls: ["notes"] });
});

test("the Settings form hides every column whose box is unticked, but never Call or Decide", () => {
  const ticked = new Set(["show:queue:judges", "show:queue:tags", "show:queue:due", "show:queue:reason", "show:queue:votes",
                          "show:calls:tags", "show:calls:filter", "show:calls:judges", "show:calls:due", "show:calls:seen"]);
  assert.deepEqual(hiddenFromForm(ticked), { queue: ["tier", "seen"], calls: ["notes"] });
  assert.deepEqual(COLUMNS.queue.filter((c) => c.fixed).map((c) => c.key), ["call", "decide"]);
  assert.deepEqual(COLUMNS.calls.filter((c) => c.fixed).map((c) => c.key), ["call", "decision"]);
});

test("tags under the title are a choice in Settings, shown by default", () => {
  assert.ok(COLUMNS.queue.some((c) => c.key === "tags" && !c.fixed));
  assert.ok(COLUMNS.calls.some((c) => c.key === "tags" && !c.fixed));
  assert.ok(!readHidden(undefined).queue.includes("tags"));
});
