import { test } from "node:test";
import assert from "node:assert/strict";
import { allowedSignIn, loginMessage, needsSession, safeFrom, signInDomain, signInEnabled } from "./signin.ts";

const USERS = [
  { name: "David Wood", email: "david@velocityexplorations.com", slackId: "U08V7ULPH1N" },
  { name: "Shaun Jones", email: "Shaun@VelocityExplorations.com", slackId: null },
  { name: "Lisa Hall", email: null, slackId: null },
  { name: "Outside Partner", email: "partner@example.com", slackId: null },
];
const DOMAIN = "velocityexplorations.com";

test("only a verified Velocity Google account whose email is on the list gets in, as its name (U7)", () => {
  const google = (email: string, over: object = {}) => ({ email, verified: true, hd: DOMAIN, ...over });
  assert.deepEqual(allowedSignIn(google("David@VelocityExplorations.com"), USERS, DOMAIN), { ok: true, name: "David Wood" });
  assert.deepEqual(allowedSignIn(google("shaun@velocityexplorations.com"), USERS, DOMAIN), { ok: true, name: "Shaun Jones" });
  assert.equal(allowedSignIn(google("david@velocityexplorations.com", { verified: false }), USERS, DOMAIN).ok, false);
  assert.equal(allowedSignIn(google("david@velocityexplorations.com", { hd: null }), USERS, DOMAIN).ok, false);   // a personal account
  assert.equal(allowedSignIn(google("stranger@velocityexplorations.com"), USERS, DOMAIN).ok, false);             // not on the list
  assert.equal(allowedSignIn(google("partner@example.com", { hd: "example.com" }), USERS, DOMAIN).ok, false);     // the wrong domain
  assert.equal(allowedSignIn({ email: null, verified: true, hd: DOMAIN }, USERS, DOMAIN).ok, false);
});

test("sign-in is on once its Google client and secret are set, and keeps to the company's domain", () => {
  assert.equal(signInEnabled({ AUTH_GOOGLE_ID: "id", AUTH_GOOGLE_SECRET: "secret", AUTH_SECRET: "s" }), true);
  assert.equal(signInEnabled({ AUTH_GOOGLE_ID: "id", AUTH_GOOGLE_SECRET: "", AUTH_SECRET: "s" }), false);
  assert.equal(signInEnabled({ AUTH_GOOGLE_ID: "id", AUTH_GOOGLE_SECRET: "secret" }), false);
  assert.equal(signInEnabled({}), false);
  assert.equal(signInDomain({}), DOMAIN);
  assert.equal(signInDomain({ DASHBOARD_DOMAIN: " Example.com " }), "example.com");
});

test("the login page says why, in words (U7)", () => {
  assert.equal(loginMessage({ reason: "signed_out" }), "You are signed out.");
  assert.equal(loginMessage({ reason: "timed_out" }), "Your session timed out. Sign in again to carry on.");
  assert.equal(loginMessage({ error: "AccessDenied" }),
    "That Google account is not on the BD Team list. Sign in with your Velocity account, or ask an admin to add you.");
  assert.equal(loginMessage({ error: "OAuthCallbackError" }), "Sign-in was cancelled.");
  assert.equal(loginMessage({ error: "Configuration" }), "Sign-in is not set up correctly. Tell an admin.");
  assert.equal(loginMessage({ error: "Something" }), "Sign-in did not finish. Try again.");
  assert.equal(loginMessage({}), null);
});

test("after sign-in a person returns only to a page of this dashboard", () => {
  assert.equal(safeFrom("/proposals?view=drafting"), "/proposals?view=drafting");
  for (const bad of [undefined, "", "https://evil.example/", "//evil.example", "/login", "/login?from=/x", "/api/auth/signout", "javascript:alert(1)"]) {
    assert.equal(safeFrom(bad), "/", String(bad));
  }
});

test("every page needs a session but the sign-in page, its Google routes and the health check", () => {
  for (const path of ["/", "/review", "/proposals/sam-1", "/profile"]) assert.equal(needsSession(path), true, path);
  for (const path of ["/login", "/api/auth/callback/google", "/api/auth/session", "/healthz", "/_next/static/chunks/a.js",
    "/velocity-mark-white.png", "/fonts/inter-tight.woff2", "/logos/sam-gov.svg", "/favicon.ico"]) assert.equal(needsSession(path), false, path);
  assert.equal(needsSession("/proposals/2026-03-17.notes"), true);   // a call id with a dot is still a page
});
