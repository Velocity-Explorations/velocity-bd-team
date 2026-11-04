import { test } from "node:test";
import assert from "node:assert/strict";
import { present } from "./schema.ts";

test("a table found once is not looked up again on later pages", async () => {
  let asked = 0;
  const look = (answer: boolean) => async () => {
    asked += 1;
    return answer;
  };
  assert.equal(await present("schema-test-found", look(true)), true);
  assert.equal(await present("schema-test-found", look(false)), true);
  assert.equal(asked, 1);
});

test("a table not there yet is looked up again, since a migration may be applied while the dashboard runs", async () => {
  let asked = 0;
  const look = (answer: boolean) => async () => {
    asked += 1;
    return answer;
  };
  assert.equal(await present("schema-test-later", look(false)), false);
  assert.equal(await present("schema-test-later", look(true)), true);
  assert.equal(await present("schema-test-later", look(false)), true);
  assert.equal(asked, 2);
});
