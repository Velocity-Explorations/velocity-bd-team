import { test } from "node:test";
import assert from "node:assert/strict";
import { CLOSED_PATTERN, filterHref, pickMany, pickSort, pickState } from "./filters.ts";
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

test("pickState reads open or closed, and still honours the old open=1 links", () => {
  assert.equal(pickState("open"), "open");
  assert.equal(pickState("closed"), "closed");
  assert.equal(pickState("both"), "");
  assert.equal(pickState(undefined, "1"), "open");
  assert.equal(pickState("closed", "1"), "closed");
  assert.equal(pickState(undefined, undefined), "");
});

test("pickSort is newest first unless closing soonest is asked for", () => {
  assert.equal(pickSort("due"), "due");
  assert.equal(pickSort("newest"), "newest");
  assert.equal(pickSort("anything"), "newest");
  assert.equal(pickSort(undefined), "newest");
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
