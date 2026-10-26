import { test } from "node:test";
import assert from "node:assert/strict";
import { choiceLinks, CLOSED_PATTERN, filterHref, nextSort, pickMany, pickSort, pickState, portalOptions, sortLink, sortParams } from "./filters.ts";
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
