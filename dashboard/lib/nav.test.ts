import { test } from "node:test";
import assert from "node:assert/strict";
import { countLabel, initials, SECTIONS } from "./nav.ts";

test("the bar has four sections, and Automation opens on Agent update requests (N1)", () => {
  assert.deepEqual(
    SECTIONS.map((s) => [s.key, s.label, s.href]),
    [["home", "Home", "/"], ["calls", "Calls", "/review"], ["proposals", "Proposals", "/proposals"], ["automation", "Automation", "/requests"]],
  );
});

test("each count chip says what it counts (N3)", () => {
  assert.equal(countLabel("calls", 28), "28 waiting for you");
  assert.equal(countLabel("proposals", 1), "1 to draft, ready for you or overdue");
  assert.equal(countLabel("automation", 1), "1 request waiting");
  assert.equal(countLabel("automation", 2), "2 requests waiting");
});

test("initials take the first and last names' first letters, or a single name's first two", () => {
  assert.equal(initials("David Wood"), "DW");
  assert.equal(initials("Shaun"), "SH");
  assert.equal(initials("  ana maria  de la cruz "), "AC");
  assert.equal(initials(""), "?");
});
