import { test } from "node:test";
import assert from "node:assert/strict";
import { POOL } from "./db.ts";

test("the pool keeps its connections for minutes between pages, so a click does not wait on a new one", () => {
  assert.ok(POOL.idle_timeout >= 300, `idle_timeout is ${POOL.idle_timeout} seconds`);
  assert.equal(POOL.prepare, false);
});
