import assert from "node:assert/strict";
import { test } from "node:test";
import { callHref, costLine, isOffline, parseAnswer, parseSources, statusLine, threadIdOk } from "./ask.ts";

test("an answer becomes paragraphs and bullet lists, with only same-site and https links made links", () => {
  const blocks = parseAnswer(
    "Unison is open.\nIt closes 4 Dec.\n\n- [Unison](/calls?q=Unison) is due 4 Dec\n- see [SAM.gov](https://sam.gov/opp/1)\n\n" +
      "Not a link: [x](javascript:alert(1)) or [y](//evil.example) or [z](http://plain.example)",
  );
  assert.equal(blocks.length, 3);
  assert.deepEqual(blocks[0], { kind: "p", lines: [[{ text: "Unison is open." }], [{ text: "It closes 4 Dec." }]] });
  assert.equal(blocks[1].kind, "ul");
  if (blocks[1].kind !== "ul") return;
  assert.deepEqual(blocks[1].items[0], [{ text: "Unison", href: "/calls?q=Unison" }, { text: " is due 4 Dec" }]);
  assert.deepEqual(blocks[1].items[1], [{ text: "see " }, { text: "SAM.gov", href: "https://sam.gov/opp/1" }]);
  if (blocks[2].kind !== "p") return;
  assert.ok(blocks[2].lines[0].every((part) => !("href" in part)));
  assert.match(blocks[2].lines[0].map((p) => p.text).join(""), /\[x\]\(javascript:alert\(1\)\)/);
});

test("an empty or missing answer gives no blocks", () => {
  assert.deepEqual(parseAnswer(""), []);
  assert.deepEqual(parseAnswer(null), []);
});

test("sources are read defensively, and each call links to its title on All calls", () => {
  assert.deepEqual(parseSources('{"calls":[{"id":"c-1","title":"Unison","portal":"SAM.gov"},{"id":5}],"facts":["F-06",3]}'),
    { calls: [{ id: "c-1", title: "Unison", portal: "SAM.gov" }], facts: ["F-06"] });
  assert.deepEqual(parseSources("not json"), { calls: [], facts: [] });
  assert.deepEqual(parseSources(null), { calls: [], facts: [] });
  assert.equal(callHref({ id: "c-1", title: "Unison & co", portal: "SAM.gov" }), "/calls?q=Unison%20%26%20co");
});

test("the line under an answer says who answered, how many tools and about what it cost", () => {
  assert.equal(costLine("grok-4.7", '[{"name":"search_calls"},{"name":"brief_call"}]', 0.0412), "grok-4.7, 2 tools, about $0.04");
  assert.equal(costLine("grok-4.7", "[]", 0.004), "grok-4.7, no tools, under $0.01");
  assert.equal(costLine("grok-4.7", '[{"name":"x"}]', null), "grok-4.7, 1 tool");
  assert.equal(costLine(null, null, null), "");
});

test("Grok is offline when the assistant has not been seen for two minutes", () => {
  const now = Date.parse("2026-11-07T15:00:00Z");
  assert.equal(isOffline("2026-11-07T14:59:00Z", now), false);
  assert.equal(isOffline("2026-11-07T14:57:30Z", now), true);
  assert.equal(isOffline(null, now), true);
});

test("the status line says what the person waits on", () => {
  const now = Date.parse("2026-11-07T15:00:00Z");
  assert.equal(statusLine("queued", "2026-11-07T14:59:50Z", now), "Grok is thinking");
  assert.equal(statusLine("working", "2026-11-07T14:59:50Z", now), "Grok is thinking");
  assert.equal(statusLine("queued", "2026-11-07T14:50:00Z", now), "Grok is offline, so the question waits until it is back");
  assert.equal(statusLine("done", null, now), "");
});

test("a thread id is one the panel could have made", () => {
  assert.equal(threadIdOk("4f6c2a0e-8d9b-4c1a-9e2f-0a1b2c3d4e5f"), true);
  assert.equal(threadIdOk("short"), false);
  assert.equal(threadIdOk("has spaces in it and more"), false);
  assert.equal(threadIdOk(null), false);
});
