import assert from "node:assert/strict";
import { test } from "node:test";
import { ASK_MAX, ASK_MIN, askCookie, askLeftOpen, askWidthCookie, askWidthCss, callHref, costLine, fitAskWidth, readAskWidth, isOffline, parseAnswer, parseSources, statusLine, threadIdOk } from "./ask.ts";

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

test("bold words show bold, without their asterisks", () => {
  const [block] = parseAnswer("Request **#1** waits for **approval** on the Requests page.");
  assert.equal(block.kind, "p");
  if (block.kind !== "p") return;
  assert.deepEqual(block.lines[0], [{ text: "Request " }, { text: "#1", strong: true }, { text: " waits for " },
    { text: "approval", strong: true }, { text: " on the Requests page." }]);
});

test("an empty or missing answer gives no blocks", () => {
  assert.deepEqual(parseAnswer(""), []);
  assert.deepEqual(parseAnswer(null), []);
});

test("sources are read defensively, and each call links to its title on All calls", () => {
  assert.deepEqual(parseSources('{"calls":[{"id":"c-1","title":"Unison","portal":"SAM.gov"},{"id":5}],"facts":["F-06",3],' +
    '"requests":[{"id":42,"kind":"rereview","summary":"Re-review Unison"},{"id":"x"}]}'),
    { calls: [{ id: "c-1", title: "Unison", portal: "SAM.gov" }], facts: ["F-06"],
      requests: [{ id: 42, kind: "rereview", summary: "Re-review Unison" }] });
  assert.deepEqual(parseSources("not json"), { calls: [], facts: [], requests: [] });
  assert.deepEqual(parseSources(null), { calls: [], facts: [], requests: [] });
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

test("the panel's cookie remembers it open from page to page, and forgets it on close", () => {
  assert.equal(askCookie(true), "ask_panel=open; path=/; max-age=31536000; samesite=lax");
  assert.equal(askCookie(false), "ask_panel=; path=/; max-age=0; samesite=lax");
  assert.equal(askLeftOpen("open"), true);
  assert.equal(askLeftOpen(""), false);
  assert.equal(askLeftOpen(undefined), false);
  assert.equal(askLeftOpen("1"), false);
});

test("a dragged width stays between 320px and 760px, and leaves the page at least 480px", () => {
  assert.equal(ASK_MIN, 320);
  assert.equal(ASK_MAX, 760);
  assert.equal(fitAskWidth(500.4, 1440), 500);
  assert.equal(fitAskWidth(100, 1440), 320);
  assert.equal(fitAskWidth(2000, 1440), 760);
  assert.equal(fitAskWidth(700, 1100), 620);   // 1100 - 480
  assert.equal(fitAskWidth(700, 700), 320);    // a window too small for both still keeps the smallest panel
});

test("the width cookie is read only when it holds a width the panel could have", () => {
  assert.equal(readAskWidth("520"), 520);
  assert.equal(readAskWidth(undefined), null);
  assert.equal(readAskWidth(""), null);
  assert.equal(readAskWidth("abc"), null);
  assert.equal(readAskWidth("100"), null);
  assert.equal(readAskWidth("9999"), null);
  assert.equal(askWidthCookie(520), "ask_width=520; path=/; max-age=31536000; samesite=lax");
  assert.equal(askWidthCookie(null), "ask_width=; path=/; max-age=0; samesite=lax");
});

test("the width's CSS sets the panel's width and when tables beside it scroll sideways", () => {
  const plain = askWidthCss(null);
  assert.match(plain, /--ask-width: ?clamp\(340px, ?30vw, ?440px\)/);
  assert.match(plain, /@media \(max-width: ?1463px\)/);
  const wide = askWidthCss(600);
  assert.match(wide, /--ask-width: ?min\(600px, ?calc\(100vw - 480px\)\)/);
  assert.match(wide, /@media \(max-width: ?1623px\)/);   // 1024px of page plus the panel, less a pixel
  assert.match(wide, /\.table-wrap ?\{ ?overflow-x: ?auto/);
});
