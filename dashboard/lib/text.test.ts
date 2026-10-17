import { test } from "node:test";
import assert from "node:assert/strict";
import { buildHref, escapeLike, firstParam, isClosed, noteLine, parseNoteLine, safeReturnTo } from "./text.ts";

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
