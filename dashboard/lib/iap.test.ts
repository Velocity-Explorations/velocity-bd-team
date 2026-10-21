import { test } from "node:test";
import assert from "node:assert/strict";
import { generateKeyPairSync, sign, type KeyObject } from "node:crypto";
import { IAP_ISSUER, keyStore, needsSignIn, verifyIapJwt, verifyIapToken, type Jwk } from "./iap.ts";

// Google's Identity-Aware Proxy signs an ES256 JWT for every request it lets through. These tests
// sign their own tokens with a P-256 key made here and hand its public half to the verifier.

const AUDIENCE = "/projects/123456789/global/backendServices/987654321";
const NOW_MS = Date.UTC(2026, 9, 21, 12, 0, 0);
const NOW_S = NOW_MS / 1000;

function keyPair(kid: string): { privateKey: KeyObject; jwk: Jwk } {
  const { privateKey, publicKey } = generateKeyPairSync("ec", { namedCurve: "P-256" });
  return { privateKey, jwk: { ...(publicKey.export({ format: "jwk" }) as Jwk), kid, alg: "ES256", use: "sig" } };
}

const GOOGLE = keyPair("k1");
const OTHER = keyPair("k1");
const KEYS = [GOOGLE.jwk];

function part(value: object): string {
  return Buffer.from(JSON.stringify(value)).toString("base64url");
}

function claims(extra: Record<string, unknown> = {}): Record<string, unknown> {
  return { iss: IAP_ISSUER, aud: AUDIENCE, iat: NOW_S - 30, exp: NOW_S + 570, email: "david@velocityexplorations.com",
           sub: "accounts.google.com:1234", ...extra };
}

function token(body: object = claims(), opts: { kid?: string; alg?: string; key?: KeyObject } = {}): string {
  const head = part({ alg: opts.alg ?? "ES256", kid: opts.kid ?? "k1", typ: "JWT" });
  const payload = part(body);
  const signature = sign("sha256", Buffer.from(head + "." + payload), { key: opts.key ?? GOOGLE.privateKey, dsaEncoding: "ieee-p1363" });
  return head + "." + payload + "." + signature.toString("base64url");
}

test("a token IAP signed for this dashboard gives the person's email", () => {
  assert.deepEqual(verifyIapJwt(token(), AUDIENCE, KEYS, NOW_MS), { ok: true, email: "david@velocityexplorations.com" });
});

test("every other token is refused, with the reason", () => {
  const refused = (jwt: string): string => {
    const result = verifyIapJwt(jwt, AUDIENCE, KEYS, NOW_MS);
    assert.equal(result.ok, false, jwt);
    return result.ok ? "" : result.reason;
  };
  assert.match(refused(token(claims({ aud: "/projects/1/global/backendServices/2" }))), /audience/);
  assert.match(refused(token(claims({ iss: "https://accounts.google.com" }))), /issuer/);
  assert.match(refused(token(claims({ exp: NOW_S - 120 }))), /expired/);
  assert.match(refused(token(claims({ iat: NOW_S + 300 }))), /future/);
  assert.match(refused(token(claims({ email: "" }))), /email/);
  assert.match(refused(token(claims(), { kid: "k9" })), /key/);
  assert.match(refused(token(claims(), { key: OTHER.privateKey })), /signature/);
  assert.match(refused(token(claims(), { alg: "HS256" })), /ES256/);
  const [head, , signature] = token().split(".");
  assert.match(refused(head + "." + part(claims({ email: "mallory@velocityexplorations.com" })) + "." + signature), /signature/);
  assert.match(refused("not-a-token"), /malformed/);
});

test("a minute of clock skew is allowed either way", () => {
  assert.equal(verifyIapJwt(token(claims({ exp: NOW_S - 30 })), AUDIENCE, KEYS, NOW_MS).ok, true);
  assert.equal(verifyIapJwt(token(claims({ iat: NOW_S + 30 })), AUDIENCE, KEYS, NOW_MS).ok, true);
});

test("Google's keys are fetched once an hour, and again for a new key id at most once a minute", async () => {
  let clock = NOW_MS;
  let fetches = 0;
  const store = keyStore(async () => {
    fetches += 1;
    return KEYS;
  }, () => clock);
  await store.forKid("k1");
  await store.forKid("k1");
  assert.equal(fetches, 1);
  await store.forKid("k2");                 // unknown, but the keys are seconds old
  assert.equal(fetches, 1);
  clock += 61_000;
  await store.forKid("k2");                 // unknown and over a minute old: fetch again
  assert.equal(fetches, 2);
  clock += 3_600_001;
  await store.forKid("k1");                 // an hour old: fetch again
  assert.equal(fetches, 3);
});

test("a request without the signed header, or when the keys cannot be fetched, is refused", async () => {
  const store = keyStore(async () => KEYS, () => NOW_MS);
  assert.deepEqual(await verifyIapToken(token(), AUDIENCE, store, NOW_MS), { ok: true, email: "david@velocityexplorations.com" });
  assert.equal((await verifyIapToken(null, AUDIENCE, store, NOW_MS)).ok, false);
  const offline = keyStore(async () => {
    throw new Error("network down");
  }, () => NOW_MS);
  const result = await verifyIapToken(token(), AUDIENCE, offline, NOW_MS);
  assert.equal(result.ok, false);
  assert.match(result.ok ? "" : result.reason, /keys/);
});

test("only the load balancer's health check skips the sign-in", () => {
  assert.equal(needsSignIn("/healthz"), false);
  for (const path of ["/", "/calls", "/judges", "/_next/static/chunks/main.js", "/healthz/extra"]) {
    assert.equal(needsSignIn(path), true, path);
  }
});
