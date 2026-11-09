import assert from "node:assert/strict";
import { test } from "node:test";
import { pictureUrl, sniffImage } from "./picture.ts";

const bytes = (...b: number[]) => new Uint8Array([...b, ...new Array(16).fill(0)]);

test("a picture is known by its first bytes, never by its name or the type the browser claims", () => {
  assert.equal(sniffImage(bytes(0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a)), "image/png");
  assert.equal(sniffImage(bytes(0xff, 0xd8, 0xff, 0xe0)), "image/jpeg");
  assert.equal(sniffImage(bytes(0x47, 0x49, 0x46, 0x38, 0x39, 0x61)), "image/gif");
  const webp = new Uint8Array(16);
  webp.set([0x52, 0x49, 0x46, 0x46], 0);
  webp.set([0x57, 0x45, 0x42, 0x50], 8);
  assert.equal(sniffImage(webp), "image/webp");
  assert.equal(sniffImage(new TextEncoder().encode("<svg xmlns='http://www.w3.org/2000/svg'></svg>")), null);
  assert.equal(sniffImage(new Uint8Array([0xff, 0xd8])), null);
});

test("a picture's address names the person and when it was set, so a new one is fetched at once", () => {
  assert.equal(pictureUrl("David Wood", "2026-11-09T12:00:00Z"), "/api/picture?name=David%20Wood&v=2026-11-09T12%3A00%3A00Z");
});
