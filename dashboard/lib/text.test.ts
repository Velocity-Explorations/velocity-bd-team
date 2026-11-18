import { test } from "node:test";
import assert from "node:assert/strict";
import {
  buildHref,
  decidedNotice,
  escapeLike,
  firstParam,
  fromQueue,
  isClosed,
  isNoteStamp,
  noteLine,
  notesByPerson,
  notesOf,
  parseNoteLine,
  safeReturnTo,
  votedHref,
  withoutTypedNote,
  writeNoteLine,
} from "./text.ts";

test("noteLine matches the pipeline's append_note format and stays on one line", () => {
  assert.equal(
    noteLine("2026-10-17T09:44:33Z", "David Wood", "  hardware\n heavy,   not us "),
    "[2026-10-17T09:44:33Z David Wood] hardware heavy, not us",
  );
  assert.equal(noteLine("2026-10-17T09:44:33Z", "David Wood", "   "), "");
});

test("escapeLike neutralises LIKE wildcards and the escape character", () => {
  assert.equal(escapeLike("50%_off\\x"), "50\\%\\_off\\\\x");
  assert.equal(escapeLike("plain words"), "plain words");
});

test("safeReturnTo only allows same-site relative paths", () => {
  assert.equal(safeReturnTo("/calls?portal=Vulcan+SOF"), "/calls?portal=Vulcan+SOF");
  assert.equal(safeReturnTo("/"), "/");
  for (const bad of ["//evil.example", "https://evil.example", "/\\evil.example", "calls", "/ok\nbad", 5, null, undefined]) {
    assert.equal(safeReturnTo(bad), "/", String(bad));
  }
});

test("isClosed reads any portal's *_closed flag from extra", () => {
  assert.equal(isClosed('{"vulcan_description_fallback": false, "vulcan_closed": true}'), true);
  assert.equal(isClosed('{"vulcan_closed": false}'), false);
  assert.equal(isClosed('{"other": true}'), false);
  assert.equal(isClosed(null), false);
  assert.equal(isClosed("not json"), false);
});

test("buildHref drops empty values", () => {
  assert.equal(buildHref("/", { portal: "Vulcan SOF", verdict: "", hide_closed: undefined }), "/?portal=Vulcan+SOF");
  assert.equal(buildHref("/calls", {}), "/calls");
});

test("firstParam takes the first value, trimmed and capped", () => {
  assert.equal(firstParam(" Vulcan SOF "), "Vulcan SOF");
  assert.equal(firstParam(["a", "b"]), "a");
  assert.equal(firstParam(undefined), "");
  assert.equal(firstParam("x".repeat(300), 10), "xxxxxxxxxx");
});

test("parseNoteLine splits the stored note format and passes anything else through", () => {
  assert.deepEqual(parseNoteLine("[2026-10-17T09:44:33Z U08V7ULPH1N] Just to note, this one seems hardware heavy"), {
    at: "2026-10-17T09:44:33Z",
    by: "U08V7ULPH1N",
    text: "Just to note, this one seems hardware heavy",
  });
  assert.deepEqual(parseNoteLine("[2026-10-17T09:50:00Z David Wood] call back Monday"), {
    at: "2026-10-17T09:50:00Z",
    by: "David Wood",
    text: "call back Monday",
  });
  assert.deepEqual(parseNoteLine("free text"), { at: null, by: null, text: "free text" });
});

const NOW = "2026-11-16T10:00:05Z";

test("a note box's first save adds a line under the person signed in, stamped now", () => {
  assert.deepEqual(writeNoteLine(null, null, "David Wood", " looks\n  promising ", NOW), {
    notes: `[${NOW} David Wood] looks promising`,
    at: NOW,
  });
  const before = "[2026-11-01T09:00:00Z U08V7ULPH1N] a Slack reply\nthat ran onto a second line";
  assert.deepEqual(writeNoteLine(before, null, "David Wood", "mine", NOW), {
    notes: `${before}\n[${NOW} David Wood] mine`,
    at: NOW,
  });
});

test("a later save from the same box edits its line in place and keeps the line's stamp", () => {
  const notes = [
    "[2026-11-16T09:00:00Z Shaun Jones] theirs",
    "[2026-11-16T09:30:00Z David Wood] draft",
    "[2026-11-16T09:40:00Z Lisa Hall] later",
  ].join("\n");
  assert.deepEqual(writeNoteLine(notes, "2026-11-16T09:30:00Z", "David Wood", "draft, finished", NOW), {
    notes: notes.replace("] draft", "] draft, finished"),
    at: "2026-11-16T09:30:00Z",
  });
});

test("emptying the box takes its note away", () => {
  const notes = "[2026-11-16T09:00:00Z Shaun Jones] theirs\n[2026-11-16T09:30:00Z David Wood] draft";
  assert.deepEqual(writeNoteLine(notes, "2026-11-16T09:30:00Z", "David Wood", "  \n ", NOW), {
    notes: "[2026-11-16T09:00:00Z Shaun Jones] theirs",
    at: null,
  });
  assert.deepEqual(writeNoteLine("[2026-11-16T09:30:00Z David Wood] draft", "2026-11-16T09:30:00Z", "David Wood", "", NOW), {
    notes: null,
    at: null,
  });
  assert.deepEqual(writeNoteLine("[2026-11-16T09:00:00Z Shaun Jones] theirs", null, "David Wood", "   ", NOW), {
    notes: "[2026-11-16T09:00:00Z Shaun Jones] theirs",
    at: null,
  });
});

test("a stamp edits only that person's line; with the line gone the note starts again", () => {
  const theirs = "[2026-11-16T09:30:00Z Shaun Jones] theirs";
  assert.deepEqual(writeNoteLine(theirs, "2026-11-16T09:30:00Z", "David Wood", "mine", NOW), {
    notes: `${theirs}\n[${NOW} David Wood] mine`,
    at: NOW,
  });
  const longer = "[2026-11-16T09:30:00Z David Woodward] his";
  assert.deepEqual(writeNoteLine(longer, "2026-11-16T09:30:00Z", "David Wood", "mine", NOW), {
    notes: `${longer}\n[${NOW} David Wood] mine`,
    at: NOW,
  });
});

test("a decision that carries the box's note takes the place of the line the box saved", () => {
  const notes = [
    "[2026-11-16T09:00:00Z David Wood] older",
    "[2026-11-16T09:20:00Z Shaun Jones] theirs",
    "[2026-11-16T09:30:00Z David Wood] hardware heavy",
  ].join("\n");
  assert.equal(withoutTypedNote(notes, "David Wood", " hardware\n heavy "),
    "[2026-11-16T09:00:00Z David Wood] older\n[2026-11-16T09:20:00Z Shaun Jones] theirs");
  assert.equal(withoutTypedNote(notes, "David Wood", "older"), notes);   // only the person's newest line
  assert.equal(withoutTypedNote(notes, "Shaun Jones", "hardware heavy"), notes);   // never someone else's
  assert.equal(withoutTypedNote(notes, "David Wood", "  "), notes);
  assert.equal(withoutTypedNote(null, "David Wood", "x"), null);
  assert.equal(withoutTypedNote("[2026-11-16T09:30:00Z David Wood] only", "David Wood", "only"), null);
});

test("notesOf reads each stamped line as a note and joins a Slack reply's later lines to it", () => {
  const notes = [
    "[2026-11-01T09:00:00Z U08V7ULPH1N] a reply",
    "that ran onto a second line",
    "",
    "[2026-11-16T09:30:00Z David Wood] call the PM",
  ].join("\n");
  assert.deepEqual(notesOf(notes), [
    { at: "2026-11-01T09:00:00Z", by: "U08V7ULPH1N", text: "a reply\nthat ran onto a second line" },
    { at: "2026-11-16T09:30:00Z", by: "David Wood", text: "call the PM" },
  ]);
  assert.deepEqual(notesOf("written by hand\n[2026-11-16T09:30:00Z David Wood] x"), [
    { at: null, by: null, text: "written by hand" },
    { at: "2026-11-16T09:30:00Z", by: "David Wood", text: "x" },
  ]);
  assert.deepEqual(notesOf(null), []);
  assert.deepEqual(notesOf(""), []);
});

test("notesByPerson groups each person's notes under the name shown on their vote, in the order they wrote them", () => {
  const notes = [
    "[2026-11-01T09:00:00Z U08V7ULPH1N] from Slack",
    "[2026-11-02T09:00:00Z Lisa Hall] hers",
    "[2026-11-03T09:00:00Z David Wood] then the dashboard",
  ].join("\n");
  const nameOf = (by: string | null) => (by === "U08V7ULPH1N" ? "David Wood" : by ?? "");
  assert.deepEqual(notesByPerson(notes, nameOf), [
    { person: "David Wood", notes: [
      { at: "2026-11-01T09:00:00Z", by: "U08V7ULPH1N", text: "from Slack" },
      { at: "2026-11-03T09:00:00Z", by: "David Wood", text: "then the dashboard" },
    ] },
    { person: "Lisa Hall", notes: [{ at: "2026-11-02T09:00:00Z", by: "Lisa Hall", text: "hers" }] },
  ]);
  assert.deepEqual(notesByPerson("by hand", nameOf), [{ person: "", notes: [{ at: null, by: null, text: "by hand" }] }]);
});

test("isNoteStamp takes only the ledger's own timestamps", () => {
  assert.equal(isNoteStamp("2026-11-16T10:00:05Z"), true);
  for (const bad of ["", "x", "2026-11-16 10:00:05", "2026-11-16T10:00:05.123Z", "2026-11-16T10:00:05Z] [", null, 5, undefined]) {
    assert.equal(isNoteStamp(bad), false, String(bad));
  }
});

test("a vote from the review queue says the call has left your queue; elsewhere it does not", () => {
  assert.equal(decidedNotice("decide", "Pursue", "PY26.2 TACFI Notice of Opportunity", "", true),
    "Pursue: PY26.2 TACFI Notice of Opportunity. It has left your queue.");
  assert.equal(decidedNotice("decide", "Pursue", "PY26.2 TACFI Notice of Opportunity", "", false),
    "Pursue: PY26.2 TACFI Notice of Opportunity");
  assert.equal(decidedNotice("add", "Not relevant", "ISOF Range 2027", " The call stays Pursue.", true),
    "Added your decision, Not relevant: ISOF Range 2027. The call stays Pursue. It has left your queue.");
  assert.equal(decidedNotice("note", "Pursue", "ISOF Range 2027", "", true), "Note added: ISOF Range 2027");
});

test("choosing the vote you already have says it is already saved (Task 1, 18 Nov 2026)", () => {
  assert.equal(decidedNotice("already", "Pursue", "ISOF Range 2027", "", false), "Already saved: Pursue on ISOF Range 2027.");
  assert.equal(decidedNotice("already", "Pursue", "ISOF Range 2027", " The call stays Not relevant.", true),
    "Already saved: Pursue on ISOF Range 2027. The call stays Not relevant.");
});

test("the link after a vote finds the call on All calls by its title", () => {
  assert.equal(votedHref("PY26.2 TACFI Notice of Opportunity"), "/calls?q=PY26.2+TACFI+Notice+of+Opportunity");
  assert.equal(votedHref("x".repeat(200)), "/calls?q=" + "x".repeat(120));   // the title filter reads 120 characters
});

test("a decision sent from Needs review, any view, counts as from the queue (PRO-571)", () => {
  assert.equal(fromQueue("/review"), true);
  assert.equal(fromQueue("/review?view=top10&portal=NSTXL"), true);
  assert.equal(fromQueue("/"), false);
  assert.equal(fromQueue("/calls?q=x"), false);
});
