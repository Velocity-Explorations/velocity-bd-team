import { test } from "node:test";
import assert from "node:assert/strict";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import {
  bandNotes,
  bandTone,
  confidenceWord,
  draftLabel,
  excerpt,
  familyLabel,
  finalChecks,
  finalGate,
  jobState,
  lineNotes,
  parseLines,
  placeholderKind,
  sectionAt,
  slopHref,
  slopView,
  type ScanRow,
} from "./slop.ts";

// A made-up report in the scanner's JSON shape: the family names, fixes and matched words are examples, not the scanner's own.
const TEXT = [
  "# White paper",
  "Sure thing, here it is.",
  "[PERSON WRITES: the opening]",
  "This is not just X; a, b and c.",
  "",
  "## 2. Technical approach",
  "We use wordtwo and wordthree.",
  "The partner is [NEEDS INPUT: the partner's name].",
  "It not only this but also that, with wordone.",
  "## 3. Work plan",
  "Then d, e and f.",
  "The objective of this topic is to develop it.",
  "Hours: [NEEDS INPUT: hours per task]",
].join("\n");

function family(label: string, tier: string, hits: number, points: number, fix: string) {
  return { label, tier, hits, distinct: hits, per_1k: hits * 0.5, fired: points > 0, points, fix };
}

function finding(family: string, tier: string, line: number, column: number, match: string, exempt = "") {
  return { rule: "example", family, tier, line, column, match, text: match, weight: 1, term: false, exempt, paragraph: 1, start: 0, end: 1 };
}

const REPORT = {
  source: "draft_v2.md", profile: "proposal", channel: "document", words: 2140, sentences: 150, band: "light",
  confidence: "full", points: 9, discourse_fired: 2, residue_label: "tool residue", percentile: null,
  thresholds: { light: 2, revise: 4, heavy: 7, calibrated: false, n: 0 },
  families: {
    contrast: family("contrast frames", "discourse", 2, 3, "Say what the thing does."),
    greet: family("chatbot greetings (example)", "discourse", 1, 0, "Start with the answer."),
    lex_a: family("GPT era words (example)", "lexicon", 1, 1, "Use the plain word."),
    lex_b: family("Claude era words (example)", "lexicon", 1, 1, "Use the plain word."),
    lex_c: family("Gemini words (example)", "lexicon", 0, 0, "Use the plain word."),
    triads: family("lists of three", "surface", 2, 0.5, "Keep the two that carry information."),
    residue: family("tool residue", "residue", 0, 0, "Delete it."),
    sourcing: family("chatbot link tags (example)", "sourcing", 0, 0, "Strip it."),
    house: family("house rules (example CLAUDE.md)", "house", 0, 0, "Rewrite it."),
    prop_overlap: family("sentence copied from the solicitation", "proposal", 1, 0, "Answer it in your own words."),
    prop_open_item: family("open placeholders", "proposal", 3, 0, "Fill it in."),
  },
  findings: [
    finding("greet", "discourse", 2, 1, "Sure thing"),
    finding("prop_open_item", "proposal", 3, 1, "[PERSON WRITES: the opening]"),
    finding("contrast", "discourse", 4, 1, "This is not just X"),
    finding("triads", "surface", 4, 21, "a, b and c"),
    finding("lex_b", "lexicon", 7, 8, "wordtwo"),
    finding("lex_b", "lexicon", 7, 20, "wordthree", "the solicitation uses this term"),
    finding("prop_open_item", "proposal", 8, 16, "[NEEDS INPUT: the partner's name]"),
    finding("contrast", "discourse", 9, 4, "not only this but also that"),
    finding("lex_a", "lexicon", 9, 40, "wordone"),
    finding("triads", "surface", 11, 6, "d, e and f"),
    finding("prop_overlap", "proposal", 12, 1, "The objective of this topic"),
    finding("prop_open_item", "proposal", 13, 8, "[NEEDS INPUT: hours per task]"),
  ],
  hot_paragraphs: [{ lines: [8, 11], findings: 3, families: ["contrast frames", "GPT era words (example)", "Claude era words (example)"] }],
};

function scan(over: Partial<ScanRow> = {}): ScanRow {
  return {
    id: 4, pursuit_id: 1, step_id: 9, draft_name: "draft_v2.md", scanned_at: "2026-11-19T23:42:00Z", words: 2140, band: "light",
    confidence: "full", points: 9, provisional: 1, ready: 0, verdict: "Not ready: 1 PERSON WRITES, 2 NEEDS INPUT; band light (provisional)",
    fixed_count: 7, result_json: JSON.stringify(REPORT), text_lines: TEXT, ...over,
  };
}

test("the verdict line comes from the stored scan, with its band, points, confidence, words and draft", () => {
  const view = slopView(scan());
  assert.equal(view.verdict, "Not ready: 1 PERSON WRITES, 2 NEEDS INPUT; band light (provisional)");
  assert.deepEqual([view.ready, view.band, view.points, view.confidence, view.words, view.provisional, view.draft, view.fixed],
    [false, "light", 9, "normal", 2140, true, "Draft v2", 7]);
  assert.equal(view.lines.length, 13);
});

test("open placeholders are listed by kind, each with its line and the section it sits in", () => {
  const view = slopView(scan());
  assert.equal(view.open, 3);
  assert.deepEqual(view.placeholders.map((p) => [p.kind, p.note, p.items.map((i) => [i.line, i.section, i.match])]), [
    ["PERSON WRITES", "text a person must write", [[3, "White paper", "[PERSON WRITES: the opening]"]]],
    ["NEEDS INPUT", "facts only you have", [[8, "2. Technical approach", "[NEEDS INPUT: the partner's name]"],
                                            [13, "3. Work plan", "[NEEDS INPUT: hours per task]"]]],
  ]);
});

test("findings are grouped by family with their fix, the dated word lists as one family, and nothing names a model", () => {
  const view = slopView(scan());
  assert.deepEqual(view.families.map((f) => [f.label, f.tier, f.hits, f.per1k, f.points]), [
    ["Contrast frames", "Discourse templates", 2, 1, 3],
    ["Overused words", "Dated word lists", 2, 1, 2],
    ["Lists of three", "Surface habits", 2, 1, 0.5],
    ["Greetings", "Discourse templates", 1, 0.5, 0],
  ]);
  assert.equal(view.families[0].fix, "Say what the thing does.");
  assert.deepEqual(view.families[1].spots, [{ line: 7, column: 8, match: "wordtwo" }, { line: 9, column: 40, match: "wordone" }]);
  assert.deepEqual(view.quiet, ["Tool residue", "Tracking parameters", "House rules"]);
  assert.equal(view.exempt, 1);
  const shown = JSON.stringify([view.families, view.faults, view.hot, view.quiet]);
  assert.doesNotMatch(shown, /GPT|Claude|Gemini|chatbot/i);
});

test("proposal faults are listed apart and open placeholders are not among them", () => {
  const view = slopView(scan());
  assert.deepEqual(view.faults.map((f) => [f.label, f.tier, f.spots]), [
    ["Sentence copied from the solicitation", "Proposal faults", [{ line: 12, column: 1, match: "The objective of this topic" }]],
  ]);
});

test("paragraphs to revise first name their section and their families, at most five", () => {
  const view = slopView(scan());
  assert.deepEqual(view.hot, [{ first: 8, last: 11, section: "2. Technical approach", findings: 3, families: ["Contrast frames", "Overused words"] }]);
  const many = { ...REPORT, hot_paragraphs: Array.from({ length: 7 }, (_, i) => ({ lines: [i + 1, i + 1], findings: 1, families: [] })) };
  assert.equal(slopView(scan({ result_json: JSON.stringify(many) })).hot.length, 5);
});

test("a scan that does not parse still shows its verdict and nothing else", () => {
  const view = slopView(scan({ result_json: "not json", text_lines: null }));
  assert.equal(view.verdict, "Not ready: 1 PERSON WRITES, 2 NEEDS INPUT; band light (provisional)");
  assert.deepEqual([view.placeholders, view.families, view.faults, view.hot, view.lines], [[], [], [], [], []]);
});

test("labels lose the names of models and chatbots, and the word lists read as overused words", () => {
  assert.equal(familyLabel("chatbot sign-offs", "discourse"), "Sign-offs");
  assert.equal(familyLabel("house rules (example CLAUDE.md)", "house"), "House rules");
  assert.equal(familyLabel("GPT-9 era words (example years)", "lexicon"), "Overused words");
  assert.equal(familyLabel("chatbot", "discourse"), "Discourse templates");
  assert.equal(familyLabel("lists of three", "surface"), "Lists of three");
});

test("placeholders are sorted into the kinds the gate counts", () => {
  assert.equal(placeholderKind("[PERSON WRITES: the opening]"), "PERSON WRITES");
  assert.equal(placeholderKind("[NEED INPUT: rates]"), "NEEDS INPUT");
  assert.equal(placeholderKind("[NEEDS EVIDENCE: the source]"), "NEEDS EVIDENCE");
  assert.equal(placeholderKind("[TBD]"), "other");
});

test("a line's section is the nearest heading above it", () => {
  const lines = TEXT.split("\n");
  assert.equal(sectionAt(lines, 1), "White paper");
  assert.equal(sectionAt(lines, 9), "2. Technical approach");
  assert.equal(sectionAt(["no heading"], 1), "");
});

test("line links are read safely and kept inside the text", () => {
  assert.deepEqual(parseLines("8", 13), { first: 8, last: 8 });
  assert.deepEqual(parseLines("8-11", 13), { first: 8, last: 11 });
  assert.deepEqual(parseLines("10-99", 13), { first: 10, last: 13 });
  for (const bad of [undefined, "", "0", "x", "12-9", "20", "1-2-3"]) assert.equal(parseLines(bad, 13), null, String(bad));
});

test("the text beside the list shows the lines around the link, the linked ones marked, with what was found on each", () => {
  const lines = TEXT.split("\n");
  assert.deepEqual(excerpt(lines, 8, 8, 2).map((l) => [l.n, l.hit]), [[6, false], [7, false], [8, true], [9, false], [10, false]]);
  assert.deepEqual(excerpt(lines, 1, 2, 2).map((l) => l.n), [1, 2, 3, 4]);
  const notes = lineNotes(slopView(scan()));
  assert.deepEqual(notes.get(8), ["NEEDS INPUT, open"]);
  assert.deepEqual(notes.get(9), ["Contrast frames", "Overused words"]);
  assert.deepEqual(notes.get(12), ["Sentence copied from the solicitation"]);
});

test("the band's notes: no band under 150 words, low confidence under 300, provisional until calibrated", () => {
  const provisional = "The band lines are provisional until they are calibrated on 20 or more Velocity proposals written from 2019 " +
    "to 2022. Ready needs no open placeholder and a band of clean or light.";
  assert.deepEqual(bandNotes({ words: 120, confidence: "none", provisional: true }), [
    "Under 150 words, so no band is given; only the placeholders and proposal faults are checked.",
  ]);
  assert.deepEqual(bandNotes({ words: 240, confidence: "low", provisional: true }), ["Under 300 words, so the band has low confidence.", provisional]);
  assert.deepEqual(bandNotes({ words: 240, confidence: "low", provisional: false }), ["Under 300 words, so the band has low confidence."]);
  assert.deepEqual(bandNotes({ words: 2140, confidence: "normal", provisional: false }), []);
});

test("words for the draft, the band and the confidence", () => {
  assert.deepEqual([draftLabel("draft_v2.md"), draftLabel("draft_final.md"), draftLabel(null)], ["Draft v2", "Final version", "the draft"]);
  assert.deepEqual(["clean", "light", "revise", "heavy", null].map(bandTone), ["good", "good", "warn", "conflict", "grey"]);
  assert.deepEqual([confidenceWord("full"), confidenceWord("low"), confidenceWord("none"), confidenceWord(null)],
    ["normal", "low", "none", "not given"]);
});

test("Check again shows queued or working, and a failure only when it is newer than the scan", () => {
  const job = { id: 1, state: "queued", requested_by: "David Wood", requested_at: "2026-11-20T00:05:00Z", started_at: null,
                finished_at: null, result: null };
  const at = "2026-11-19T23:42:00Z";
  assert.equal(jobState(job, at), "queued");
  assert.equal(jobState({ ...job, state: "working" }, at), "working");
  assert.equal(jobState({ ...job, state: "failed", finished_at: "2026-11-20T00:06:00Z" }, at), "failed");
  assert.equal(jobState({ ...job, state: "failed", finished_at: "2026-11-19T20:00:00Z" }, at), null);
  assert.equal(jobState({ ...job, state: "done", finished_at: "2026-11-20T00:06:00Z" }, at), null);
  assert.equal(jobState(null, at), null);
});

// PW23: the check reports writing patterns and their fixes only. No screen, file or message says or implies that a
// text was or was not written by AI, and none shows a probability of it.
const BANNED = /written by AI|AI-generated|AI-written|probability|likely AI|by an AI|human-written/i;

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.(ts|tsx)$/.test(name) && !name.endsWith(".test.ts") ? [path] : [];
  });
}

test("no template or message on the dashboard speaks of AI authorship or its probability", () => {
  const root = join(import.meta.dirname, "..");
  const files = ["app", "components", "lib"].flatMap((dir) => sources(join(root, dir)));
  assert.ok(files.some((f) => f.endsWith("slop.ts")) && files.some((f) => f.endsWith("SlopResult.tsx")));
  const found = files.filter((f) => BANNED.test(readFileSync(f, "utf8")));
  assert.deepEqual(found, []);
});

test("line links open the result page at a line or a range, back at the item that was clicked", () => {
  assert.equal(slopHref("reviews"), "?step=reviews&view=slop");
  assert.equal(slopHref("reviews", 3, 3, "p-3"), "?step=reviews&view=slop&lines=3#p-3");
  assert.equal(slopHref("final", 86, 94, "h-1"), "?step=final&view=slop&lines=86-94#h-1");
});


test("Final checks is approved only once the newest scan of the final version says Ready (PW13, PW21)", () => {
  assert.equal(finalGate(null), "No AI slop check of the final version is saved yet. Choose Check again.");
  assert.equal(finalGate(scan({ draft_name: "draft_v2.md", ready: 1 })), "No AI slop check of the final version is saved yet. Choose Check again.");
  assert.equal(finalGate(scan({ draft_name: "draft_final.md" })),
    "The AI slop check says Not ready: 1 PERSON WRITES, 2 NEEDS INPUT; band light (provisional). Fill what is left in the final version, then choose Check again.");
  assert.equal(finalGate(scan({ draft_name: "draft_final.md", ready: 1, verdict: "Ready: band light (provisional)" })), null);
});

test("a newer scan of the final version updates the placeholder sweep and the slop check's final pass", () => {
  const checks = [
    { check: "Formatting check", ok: true, result: "done", detail: "ran" },
    { check: "Placeholder sweep", ok: false, result: "3 left", detail: "1 PERSON WRITES, 2 NEEDS INPUT, for David Wood" },
    { check: "AI slop check, final pass", ok: false, result: "not ready", detail: "Not ready: 3 placeholders" },
  ];
  const ready = scan({ draft_name: "draft_final.md", ready: 1, verdict: "Ready: band light (provisional)", scanned_at: "2026-11-20T10:00:00Z",
                       result_json: JSON.stringify({ ...REPORT, findings: [] }) });
  assert.deepEqual(finalChecks(checks, ready, "2026-11-19T10:00:00Z").map((c) => [c.check, c.result, c.ok, c.detail]), [
    ["Formatting check", "done", true, "ran"],
    ["Placeholder sweep", "none left", true, "none left, checked again"],
    ["AI slop check, final pass", "ready", true, "Ready: band light (provisional), checked again"],
  ]);
  assert.deepEqual(finalChecks(checks, ready, "2026-11-21T10:00:00Z"), checks);   // the step is newer than the scan
  assert.deepEqual(finalChecks(checks, scan({ draft_name: "draft_v2.md", scanned_at: "2026-11-20T10:00:00Z" }), "2026-11-19T10:00:00Z"), checks);
});
