import { test } from "node:test";
import assert from "node:assert/strict";
import { pastWorkGroups, pastWorkLabel, type PastWorkItem } from "./pastwork.ts";

function item(id: string, path: string, mime = "application/pdf"): PastWorkItem {
  return { id, name: path.split("/").at(-1) ?? path, path, mime, web_link: `https://drive.example.invalid/${id}`, modified_at: null };
}

const FOLDER = "application/vnd.google-apps.folder";
const ITEMS = [
  item("a", "Submissions/2026-03-17_vulcan-sof_vigilant-eagle-27", FOLDER),
  item("b", "Submissions/2026-03-17_vulcan-sof_vigilant-eagle-27/01_submitted/white-paper.pdf"),
  item("c", "Submissions/2026-04-03_vulcan-sof_northern-edge-27", FOLDER),
  item("d", "01 Company Reference/Bios/David Wood bio.docx"),
  item("e", "01 Company Reference/Capabilities.pdf"),
];

test("past work groups into submissions, newest first, and company reference; the submitted files stay out", () => {
  const groups = pastWorkGroups(ITEMS, []);
  assert.deepEqual(groups.map((g) => [g.title, g.items.map((i) => i.id)]), [
    ["Past submissions", ["c", "a"]],
    ["Company reference", ["d", "e"]],
  ]);
});

test("what is chosen already is left out", () => {
  const groups = pastWorkGroups(ITEMS, ["c", "e"]);
  assert.deepEqual(groups.map((g) => g.items.map((i) => i.id)), [["a"], ["d"]]);
  assert.deepEqual(pastWorkGroups([], []), []);
});

test("a submission reads by its date, portal and title; a reference file by its folder", () => {
  assert.equal(pastWorkLabel(ITEMS[0]), "Vigilant eagle 27, Vulcan SOF, 2026-03-17");
  assert.equal(pastWorkLabel(ITEMS[3]), "David Wood bio.docx (Bios)");
  assert.equal(pastWorkLabel(ITEMS[4]), "Capabilities.pdf");
  assert.equal(pastWorkLabel(item("x", "Submissions/odd-name", FOLDER)), "odd-name");
});

test("an undated submission reads as having no date and comes after the dated ones", () => {
  const undated = item("u", "Submissions/nodate_dsip_edge-translation", FOLDER);
  assert.equal(pastWorkLabel(undated), "Edge translation, DSIP, no date");
  assert.deepEqual(pastWorkGroups([undated, ...ITEMS], [])[0].items.map((i) => i.id), ["c", "a", "u"]);
});
