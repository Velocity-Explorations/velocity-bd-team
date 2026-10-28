import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

// The container image must never carry .env.local (it holds DATABASE_URL) or a local build.

test(".dockerignore keeps local settings and build output out of the image", () => {
  const lines = readFileSync(new URL("../.dockerignore", import.meta.url), "utf8")
    .split(/\r?\n/)
    .map((line) => line.trim());
  for (const pattern of [".env*", "node_modules", ".next"]) {
    assert.ok(lines.includes(pattern), pattern);
  }
  assert.ok(!lines.some((line) => line.startsWith("!")), "nothing is let back in");
});

// Next's standalone build leaves public/ behind, and the theme's fonts live there (PRO-569).
test("the image carries public/, where the fonts are", () => {
  const dockerfile = readFileSync(new URL("../Dockerfile", import.meta.url), "utf8");
  assert.match(dockerfile, /^COPY --from=build --chown=node:node \/app\/public \.\/public$/m);
});
