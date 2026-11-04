import { test } from "node:test";
import assert from "node:assert/strict";
import {
  choiceLinks, CLOSED_PATTERN, filterHref, nextSort, PAGE_SIZE, pageHref, pager, pickMany, pickPage, pickSort, pickState, portalOptions,
  showing, sortChoices, sortLink, sortParams,
} from "./filters.ts";
import { isClosed } from "./text.ts";

const PORTALS = ["SAM.gov", "Vulcan SOF"];

test("pickMany keeps every known value of a repeated param, once each, in the order given", () => {
  assert.deepEqual(pickMany(["Vulcan SOF", " SAM.gov ", "Vulcan SOF"], PORTALS), ["Vulcan SOF", "SAM.gov"]);
  assert.deepEqual(pickMany("Vulcan SOF", PORTALS), ["Vulcan SOF"]);
});

test("pickMany drops unknown and empty values", () => {
  assert.deepEqual(pickMany(["Nope", "", "SAM.gov"], PORTALS), ["SAM.gov"]);
  assert.deepEqual(pickMany(undefined, PORTALS), []);
});

test("portalOptions lists every scanned portal with its call count, 0 when it stored none", () => {
  assert.deepEqual(
    portalOptions(["SAM.gov", "DOE SBIR", "SAM.gov", " "], [{ portal: "SAM.gov", calls: 4 }, { portal: "Vulcan SOF", calls: 61 }]),
    [{ name: "DOE SBIR", calls: 0 }, { name: "SAM.gov", calls: 4 }, { name: "Vulcan SOF", calls: 61 }],
  );
  assert.deepEqual(portalOptions([], []), []);
});

test("pickState reads open or closed, and still honours the old open=1 links", () => {
  assert.equal(pickState("open"), "open");
  assert.equal(pickState("closed"), "closed");
  assert.equal(pickState("both"), "");
  assert.equal(pickState(undefined, "1"), "open");
  assert.equal(pickState("closed", "1"), "closed");
  assert.equal(pickState(undefined, undefined), "");
});

test("pickSort reads a column and a direction, each column starting in its natural direction", () => {
  assert.deepEqual(pickSort(undefined, undefined), { key: "seen", dir: "desc" });
  assert.deepEqual(pickSort("newest", undefined), { key: "seen", dir: "desc" });   // links from before the headers
  assert.deepEqual(pickSort("due", undefined), { key: "due", dir: "asc" });
  assert.deepEqual(pickSort("title", "desc"), { key: "title", dir: "desc" });
  assert.deepEqual(pickSort("verdict", "sideways"), { key: "verdict", dir: "asc" });
  assert.deepEqual(pickSort("anything", "asc"), { key: "seen", dir: "desc" });
  assert.deepEqual(pickSort("decision", undefined, ["seen", "due"]), { key: "seen", dir: "desc" });   // not on this page
});

test("a header reverses its own sort and starts another column in that column's direction", () => {
  assert.deepEqual(nextSort({ key: "due", dir: "asc" }, "due"), { key: "due", dir: "desc" });
  assert.deepEqual(nextSort({ key: "due", dir: "desc" }, "due"), { key: "due", dir: "asc" });
  assert.deepEqual(nextSort({ key: "due", dir: "asc" }, "seen"), { key: "seen", dir: "desc" });
});

test("links leave out the default sort and a column's natural direction", () => {
  assert.deepEqual(sortParams({ key: "seen", dir: "desc" }), { sort: "", dir: "" });
  assert.deepEqual(sortParams({ key: "due", dir: "asc" }), { sort: "due", dir: "" });
  assert.deepEqual(sortParams({ key: "due", dir: "desc" }), { sort: "due", dir: "desc" });
});

test("a sort link keeps the filters, and a menu choice changes only its own filter", () => {
  assert.deepEqual(sortLink("/calls", { q: "C2", sort: "", dir: "" }, { key: "seen", dir: "desc" }, "due"),
    { href: "/calls?q=C2&sort=due", active: false, dir: "asc" });
  assert.deepEqual(sortLink("/calls", { q: "C2", sort: "due", dir: "" }, { key: "due", dir: "asc" }, "due"),
    { href: "/calls?q=C2&sort=due&dir=desc", active: true, dir: "asc" });
  const params = { portal: ["Vulcan SOF"], verdict: "yes", sort: "due" };
  assert.deepEqual(choiceLinks("/", params, "verdict", [{ value: "", label: "Any" }, { value: "maybe", label: "Maybe" }], "yes"), [
    { label: "Any", href: "/?portal=Vulcan+SOF&sort=due", active: false },
    { label: "Maybe", href: "/?portal=Vulcan+SOF&verdict=maybe&sort=due", active: false },
  ]);
  assert.equal(choiceLinks("/", params, "verdict", [{ value: "yes", label: "Yes" }], "yes")[0].active, true);
});

test("filterHref repeats list params and skips empty ones", () => {
  assert.equal(
    filterHref("/", { portal: ["Vulcan SOF", "SAM.gov"], state: "open", sort: "" }),
    "/?portal=Vulcan+SOF&portal=SAM.gov&state=open",
  );
  assert.equal(filterHref("/calls", { portal: [], state: "", q: "" }), "/calls");
});

test("the SQL closed pattern agrees with isClosed on the ledger's JSON", () => {
  const closed = new RegExp(CLOSED_PATTERN);
  for (const extra of ['{"vulcan_closed": true}', '{"vulcan_tags": ["AI"], "vulcan_closed":true}']) {
    assert.equal(closed.test(extra), true, extra);
    assert.equal(isClosed(extra), true, extra);
  }
  for (const extra of ['{"vulcan_closed": false}', '{"vulcan_tags": ["closed"]}', "{}"]) {
    assert.equal(closed.test(extra), false, extra);
    assert.equal(isClosed(extra), false, extra);
  }
});

test("a view with its own default sort leaves that one out of links and writes the usual default out (PRO-570)", () => {
  const dueFirst = { key: "due", dir: "asc" } as const;
  assert.deepEqual(pickSort(undefined, undefined, undefined, dueFirst), dueFirst);
  assert.deepEqual(pickSort("seen", undefined, undefined, dueFirst), { key: "seen", dir: "desc" });
  assert.deepEqual(sortParams(dueFirst, dueFirst), { sort: "", dir: "" });
  assert.deepEqual(sortParams({ key: "seen", dir: "desc" }, dueFirst), { sort: "seen", dir: "" });
  assert.equal(sortLink("/review", { view: "due-soon" }, dueFirst, "seen", dueFirst).href, "/review?view=due-soon&sort=seen");
  assert.equal(sortLink("/review", { view: "due-soon" }, { key: "seen", dir: "desc" }, "due", dueFirst).href, "/review?view=due-soon");
});

test("a header menu offers the column's two sorts in words, the one in force marked (PRO-572)", () => {
  const items = sortChoices("/calls", { q: "space" }, { key: "title", dir: "asc" }, "title");
  assert.deepEqual(items, [
    { label: "Sort A to Z", href: "/calls?q=space&sort=title", active: true },
    { label: "Sort Z to A", href: "/calls?q=space&sort=title&dir=desc", active: false },
  ]);
  const due = sortChoices("/review", { view: "due-soon" }, { key: "due", dir: "asc" }, "due", { key: "due", dir: "asc" });
  assert.deepEqual(due.map((i) => [i.label, i.href, i.active]), [
    ["Sort closing soonest first", "/review?view=due-soon", true],
    ["Sort closing latest first", "/review?view=due-soon&sort=due&dir=desc", false],
  ]);
  assert.deepEqual(sortChoices("/review", {}, { key: "seen", dir: "desc" }, "seen").map((i) => i.label), ["Sort newest first", "Sort oldest first"]);
});

test("a page holds 50 calls, so a table loads in about a second instead of four", () => {
  assert.equal(PAGE_SIZE, 50);
});

test("pickPage reads a whole page number from 1; anything else is the first page", () => {
  assert.equal(pickPage("3"), 3);
  assert.equal(pickPage(["2", "5"]), 2);
  for (const raw of [undefined, "", "0", "-1", "1.5", "two", "1e3", "100001"]) assert.equal(pickPage(raw), 1, String(raw));
});

test("pageHref keeps the view and leaves the page out on the first page", () => {
  const params = { portal: ["SAM.gov"], sort: "due" };
  assert.equal(pageHref("/calls", params, 1), "/calls?portal=SAM.gov&sort=due");
  assert.equal(pageHref("/calls", params, 3), "/calls?portal=SAM.gov&sort=due&page=3");
  assert.equal(pageHref("/review", {}, 2), "/review?page=2");
});

test("pager says which calls a page holds and links the pages either side, keeping the view", () => {
  assert.deepEqual(pager("/calls", { tag: "C2" }, 2, 120), {
    page: 2, pages: 3, from: 51, to: 100, total: 120, prev: "/calls?tag=C2", next: "/calls?tag=C2&page=3", nextCount: 20,
  });
});

test("pager has no link before the first page or after the last", () => {
  assert.deepEqual(pager("/review", {}, 1, 120), { page: 1, pages: 3, from: 1, to: 50, total: 120, prev: null, next: "/review?page=2", nextCount: 50 });
  assert.deepEqual(pager("/review", {}, 3, 120), { page: 3, pages: 3, from: 101, to: 120, total: 120, prev: "/review?page=2", next: null, nextCount: 0 });
});

test("pager on a list that fits one page, or an empty one, has no links", () => {
  assert.deepEqual(pager("/calls", {}, 1, 12), { page: 1, pages: 1, from: 1, to: 12, total: 12, prev: null, next: null, nextCount: 0 });
  assert.deepEqual(pager("/calls", {}, 1, 0), { page: 1, pages: 1, from: 0, to: 0, total: 0, prev: null, next: null, nextCount: 0 });
});

test("showing gives the bar's count, with the page's span once there is more than one page", () => {
  assert.equal(showing(pager("/calls", {}, 2, 120)), "Showing 51 to 100 of 120");
  assert.equal(showing(pager("/calls", {}, 1, 12)), "Showing 12 of 12");
  assert.equal(showing(pager("/calls", {}, 1, 0)), "Showing 0 of 0");
});
