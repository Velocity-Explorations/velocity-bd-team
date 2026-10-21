import { createPublicKey, verify, type JsonWebKey } from "node:crypto";

// Google's Identity-Aware Proxy (IAP) in front of the hosted dashboard. IAP signs an ES256 JWT for
// every request it lets through and sends it in IAP_HEADER. Only that signature proves a request
// came through IAP: the plain email header it also sends can be set by anything that reaches the
// container another way. DASHBOARD_IAP_AUDIENCE turns this on (lib/viewer.ts, proxy.ts).
// Only node:crypto is imported, so `node --test` can load it directly.

export const IAP_HEADER = "x-goog-iap-jwt-assertion";
export const IAP_ISSUER = "https://cloud.google.com/iap";
export const IAP_KEYS_URL = "https://www.gstatic.com/iap/verify/public_key-jwk";
/** The load balancer's health check path: it does not pass through IAP. */
export const HEALTH_PATH = "/healthz";

const SKEW_S = 60;
const KEYS_MAX_AGE_MS = 60 * 60 * 1000;
const KEYS_RETRY_MS = 60 * 1000;

export type Jwk = { kid: string; kty: string; crv?: string; x?: string; y?: string; alg?: string; use?: string };
export type Verified = { ok: true; email: string } | { ok: false; reason: string };
export type KeyStore = { forKid(kid: string): Promise<Jwk[]> };

function refuse(reason: string): Verified {
  return { ok: false, reason };
}

function decode(part: string): Record<string, unknown> {
  return JSON.parse(Buffer.from(part, "base64url").toString("utf8")) as Record<string, unknown>;
}

/** Checks one token against Google's keys: signature, issuer, audience and times. */
export function verifyIapJwt(token: string, audience: string, keys: Jwk[], nowMs: number): Verified {
  const parts = token.split(".");
  if (parts.length !== 3) return refuse("malformed token");
  const [head, payload, signature] = parts;
  let header: Record<string, unknown>;
  let claims: Record<string, unknown>;
  try {
    header = decode(head);
    claims = decode(payload);
  } catch {
    return refuse("malformed token");
  }
  if (header.alg !== "ES256") return refuse(`algorithm ${String(header.alg)} is not ES256`);
  const jwk = keys.find((key) => key.kid === header.kid);
  if (!jwk) return refuse("unknown signing key");
  let signed = false;
  try {
    const key = createPublicKey({ key: jwk as JsonWebKey, format: "jwk" });
    signed = verify("sha256", Buffer.from(`${head}.${payload}`), { key, dsaEncoding: "ieee-p1363" }, Buffer.from(signature, "base64url"));
  } catch {
    signed = false;
  }
  if (!signed) return refuse("bad signature");
  if (claims.iss !== IAP_ISSUER) return refuse("wrong issuer");
  const aud = claims.aud;
  if (!(aud === audience || (Array.isArray(aud) && aud.includes(audience)))) return refuse("wrong audience");
  const now = nowMs / 1000;
  if (typeof claims.exp !== "number" || claims.exp < now - SKEW_S) return refuse("expired");
  if (typeof claims.iat !== "number" || claims.iat > now + SKEW_S) return refuse("issued in the future");
  if (typeof claims.email !== "string" || !claims.email) return refuse("no email");
  return { ok: true, email: claims.email };
}

/**
 * Google's signing keys, fetched again after an hour, or after a minute when a token names a key
 * we do not have yet (Google rotates them). A failed fetch is not retried for a minute.
 */
export function keyStore(fetchKeys: () => Promise<Jwk[]>, now: () => number = Date.now): KeyStore {
  let keys: Jwk[] = [];
  let fetchedAt = Number.NEGATIVE_INFINITY; // last attempt, successful or not
  let pending: Promise<void> | null = null;
  const refresh = (): Promise<void> => {
    if (!pending) {
      fetchedAt = now();
      pending = Promise.resolve()
        .then(fetchKeys)
        .then((fresh) => {
          keys = fresh;
        })
        .finally(() => {
          pending = null;
        });
    }
    return pending;
  };
  return {
    async forKid(kid: string): Promise<Jwk[]> {
      const age = now() - fetchedAt;
      if (age > KEYS_MAX_AGE_MS || (age > KEYS_RETRY_MS && !keys.some((key) => key.kid === kid))) await refresh();
      return keys;
    },
  };
}

async function fetchGoogleKeys(): Promise<Jwk[]> {
  const response = await fetch(IAP_KEYS_URL, { cache: "no-store", signal: AbortSignal.timeout(5000) });
  if (!response.ok) throw new Error(`IAP keys: HTTP ${response.status}`);
  const body = (await response.json()) as { keys?: Jwk[] };
  return body.keys ?? [];
}

const holder = globalThis as unknown as { __iapKeys?: KeyStore };

/** One key cache per server process. */
export function googleKeys(): KeyStore {
  holder.__iapKeys ??= keyStore(fetchGoogleKeys);
  return holder.__iapKeys;
}

/** The email IAP vouches for in this request's signed header, or why it was refused. */
export async function verifyIapToken(token: string | null | undefined, audience: string, store: KeyStore,
                                     nowMs: number = Date.now()): Promise<Verified> {
  if (!token) return refuse("no signed header from the sign-in proxy");
  let kid: unknown;
  try {
    kid = decode(token.split(".")[0]).kid;
  } catch {
    return refuse("malformed token");
  }
  let keys: Jwk[];
  try {
    keys = await store.forKid(String(kid));
  } catch {
    return refuse("could not fetch Google's IAP keys");
  }
  return verifyIapJwt(token, audience, keys, nowMs);
}

/** Every path needs IAP's signed header except the health check. */
export function needsSignIn(pathname: string): boolean {
  return pathname !== HEALTH_PATH;
}
