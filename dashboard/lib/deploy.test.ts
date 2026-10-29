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

// The dashboard on the scan PC until GKE (compose.yml): its container and a Cloudflare Tunnel. The repo is
// public, so the file holds no setting and no public address; both live in git-ignored files.
test("compose.yml runs the dashboard and a pinned tunnel, with settings only from git-ignored files", () => {
  const compose = readFileSync(new URL("../compose.yml", import.meta.url), "utf8");
  assert.match(compose, /^ +image: cloudflare\/cloudflared:\d{4}\.\d+\.\d+$/m, "the tunnel's image is pinned");
  assert.match(compose, /^ +env_file: \.env\.hosted$/m);
  assert.match(compose, /^ +env_file: \.env\.tunnel$/m);
  assert.equal((compose.match(/^ +restart: unless-stopped$/gm) ?? []).length, 2, "both come back with Docker");
  const published = [...compose.matchAll(/^ +- "([\d.]+:\d+:\d+)"/gm)].map((m) => m[1]);
  assert.ok(published.length > 0 && published.every((p) => p.startsWith("127.0.0.1:")), "published to this PC only");
  assert.doesNotMatch(compose, /^ +environment:/m, "no settings typed into the file");
  assert.doesNotMatch(compose, /https?:\/\/(?!127\.0\.0\.1)/, "no public address in the file");
  for (const name of [".gitignore", ".dockerignore"]) {
    const lines = readFileSync(new URL(`../${name}`, import.meta.url), "utf8").split(/\r?\n/).map((line) => line.trim());
    assert.ok(lines.includes(".env*"), `${name} keeps .env.hosted and .env.tunnel out`);
  }
});
