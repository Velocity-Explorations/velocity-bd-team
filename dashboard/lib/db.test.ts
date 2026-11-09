import { test } from "node:test";
import assert from "node:assert/strict";
import { POOL, poolSize } from "./db.ts";

test("the pool keeps its connections for minutes between pages, so a click does not wait on a new one", () => {
  assert.ok(POOL.idle_timeout >= 300, `idle_timeout is ${POOL.idle_timeout} seconds`);
  assert.equal(POOL.prepare, false);
});

test("a page's queries and its frame's run together, not three at a time", () => {
  assert.ok(POOL.max >= 8, `max is ${POOL.max}`);
});

test("a second dashboard on the same ledger, such as a test server, can hold fewer connections", () => {
  assert.equal(poolSize(undefined), 8);
  assert.equal(poolSize(""), 8);
  assert.equal(poolSize("3"), 3);
  assert.equal(poolSize("0"), 8);
  assert.equal(poolSize("lots"), 8);
  assert.equal(poolSize("40"), 8);   // never more than the default
});
