import { test } from "node:test";
import assert from "node:assert/strict";
import { descriptionCell, detailSources, splitDetails } from "./description.ts";

const LONG = "A".repeat(250) + " " + "B".repeat(100);

test("a portal's own text shows its first 300 characters, the rest on hover (Q13)", () => {
  const cell = descriptionCell("Vulcan SOF", LONG, null);
  assert.equal(cell.label, null);
  assert.equal(cell.text, LONG.slice(0, 300).trimEnd() + "…");
  assert.equal(cell.full, LONG);
  assert.deepEqual(descriptionCell("SAM.gov", "  Short.  ", null), { label: null, text: "Short.", full: "Short." });
});

test("text the scanner wrote is labelled Scanner summary", () => {
  for (const portal of ["AFWERX", "SpaceWERX", "APFIT", "NASA Forecast"]) {
    assert.equal(descriptionCell(portal, "Written by the adapter.", null).label, "Scanner summary");
  }
});

test("a members-only page says Members only in place of its placeholder", () => {
  const extra = JSON.stringify({ nstxl_members_only: true });
  const cell = descriptionCell("NSTXL", "Member-only page on NSTXL: sign in as a member to read it.", extra);
  assert.deepEqual(cell, { label: "Members only", text: "", full: "Member-only page on NSTXL: sign in as a member to read it." });
  assert.equal(descriptionCell("NSTXL", "Open project text.", "{}").label, null);
});

test("no description gives an empty cell", () => {
  assert.deepEqual(descriptionCell("DIU", null, null), { label: null, text: "", full: "" });
});

test("the details line keeps plain facts; badges go to their own line", () => {
  const { facts, badges } = splitDetails([
    { text: "Solicitation" },
    { text: "members only", tone: "warn", title: "x" },
    { text: "Kelli Brooks", href: "mailto:k@example.invalid" },
    { text: "Space Force", tone: "info" },
  ]);
  assert.deepEqual(facts.map((d) => d.text), ["Solicitation", "Kelli Brooks"]);
  assert.deepEqual(badges.map((d) => d.text), ["members only", "Space Force"]);
});

test("the reasons panel lists where each detail comes from, and the deadline's source (PRO-572)", () => {
  assert.deepEqual(
    detailSources(
      [{ text: "DEPT OF THE ARMY", title: "DEPT OF DEFENSE, DEPT OF THE ARMY" }, { text: "Solicitation" }, { text: "members only", tone: "warn", title: "Sign in to read" }],
      "From the page: Proposals are due 1 Dec.",
    ),
    [
      { text: "DEPT OF THE ARMY", source: "DEPT OF DEFENSE, DEPT OF THE ARMY" },
      { text: "members only", source: "Sign in to read" },
      { text: "Deadline", source: "From the page: Proposals are due 1 Dec." },
    ],
  );
  assert.deepEqual(detailSources([{ text: "x" }], null), []);
});
