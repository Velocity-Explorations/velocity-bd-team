import { test } from "node:test";
import assert from "node:assert/strict";
import { cacheMs, forget, remember } from "./remember.ts";

test("a read is kept for its time, then read again", async () => {
  let now = 1000;
  let reads = 0;
  const read = async () => ++reads;
  assert.equal(await remember("test-kept", 60_000, read, () => now), 1);
  now += 59_000;
  assert.equal(await remember("test-kept", 60_000, read, () => now), 1);
  now += 2_000;
  assert.equal(await remember("test-kept", 60_000, read, () => now), 2);
});

test("pages asking at once share one read", async () => {
  let reads = 0;
  const read = async () => ++reads;
  const [a, b] = await Promise.all([remember("test-shared", 60_000, read), remember("test-shared", 60_000, read)]);
  assert.equal(a, 1);
  assert.equal(b, 1);
  assert.equal(reads, 1);
});

test("a failed read is not kept", async () => {
  let reads = 0;
  const read = async () => {
    reads += 1;
    if (reads === 1) throw new Error("ledger unreachable");
    return reads;
  };
  await assert.rejects(remember("test-failed", 60_000, read));
  assert.equal(await remember("test-failed", 60_000, read), 2);
});

test("forget drops a name and everything kept under it, so the next page reads fresh", async () => {
  let reads = 0;
  const read = async () => ++reads;
  await remember("test-person:a@example.invalid", 60_000, read);
  await remember("test-person:b@example.invalid", 60_000, read);
  await remember("test-personal", 60_000, read);
  forget("test-person");
  assert.equal(await remember("test-person:a@example.invalid", 60_000, read), 4);
  assert.equal(await remember("test-personal", 60_000, read), 3);   // another name that only starts the same
});

test("DASHBOARD_CACHE_SECONDS sets how long reads are kept; 0 keeps none, as the workspace tests need", () => {
  assert.equal(cacheMs({}), 60_000);
  assert.equal(cacheMs({ DASHBOARD_CACHE_SECONDS: "0" }), 0);
  assert.equal(cacheMs({ DASHBOARD_CACHE_SECONDS: "15" }), 15_000);
  assert.equal(cacheMs({ DASHBOARD_CACHE_SECONDS: "soon" }), 60_000);
});

test("a time of 0 reads every time", async () => {
  let reads = 0;
  const read = async () => ++reads;
  await remember("test-off", 0, read);
  assert.equal(await remember("test-off", 0, read), 2);
});
