import { test } from "node:test";
import assert from "node:assert/strict";
import { aliasesFor, displayPerson, parseUsers, pickViewer } from "./people.ts";

const USERS = parseUsers("David Wood=U08V7ULPH1N, Aisha");

test("parseUsers reads names with optional Slack ids, trims, skips blanks, dedupes", () => {
  assert.deepEqual(parseUsers("David Wood=U08V7ULPH1N, Aisha ,, Bob=, Aisha"), [
    { name: "David Wood", email: null, slackId: "U08V7ULPH1N" },
    { name: "Aisha", email: null, slackId: null },
    { name: "Bob", email: null, slackId: null },
  ]);
  assert.deepEqual(parseUsers(undefined), []);
  assert.deepEqual(parseUsers("   "), []);
});

const TEAM = parseUsers("David Wood <David@VelocityExplorations.com>=U08V7ULPH1N, Shaun <shaun@velocityexplorations.com>, Aisha");

test("parseUsers reads an optional email in angle brackets before the Slack id", () => {
  assert.deepEqual(TEAM, [
    { name: "David Wood", email: "David@VelocityExplorations.com", slackId: "U08V7ULPH1N" },
    { name: "Shaun", email: "shaun@velocityexplorations.com", slackId: null },
    { name: "Aisha", email: null, slackId: null },
  ]);
});

test("behind a sign-in proxy an email names the person, in any case, with or without IAP's prefix", () => {
  assert.equal(pickViewer({ users: TEAM, headerMode: true, headerValue: "david@velocityexplorations.com" }), "David Wood");
  assert.equal(pickViewer({ users: TEAM, headerMode: true, headerValue: "accounts.google.com:SHAUN@velocityexplorations.com" }), "Shaun");
  assert.equal(pickViewer({ users: TEAM, headerMode: true, headerValue: "Aisha" }), "Aisha");
  assert.equal(pickViewer({ users: TEAM, headerMode: true, headerValue: "accounts.google.com:mallory@velocityexplorations.com" }), null);
  assert.equal(pickViewer({ users: [], headerMode: true, headerValue: "accounts.google.com:someone@velocityexplorations.com" }), "someone@velocityexplorations.com");
});

test("a single allowlisted user is the default viewer", () => {
  assert.equal(pickViewer({ users: parseUsers("David Wood"), headerMode: false }), "David Wood");
});

test("with several users the cookie decides, and only allowlisted names count", () => {
  assert.equal(pickViewer({ users: USERS, headerMode: false, cookieValue: "Aisha" }), "Aisha");
  assert.equal(pickViewer({ users: USERS, headerMode: false, cookieValue: "Mallory" }), null);
  assert.equal(pickViewer({ users: USERS, headerMode: false }), null);
});

test("header mode uses only the header, checked against the allowlist when there is one", () => {
  assert.equal(pickViewer({ users: USERS, headerMode: true, headerValue: "Aisha", cookieValue: "David Wood" }), "Aisha");
  assert.equal(pickViewer({ users: USERS, headerMode: true, headerValue: "Mallory" }), null);
  assert.equal(pickViewer({ users: USERS, headerMode: true, cookieValue: "Aisha" }), null);
  assert.equal(pickViewer({ users: [], headerMode: true, headerValue: "someone@velocityexplorations.com" }), "someone@velocityexplorations.com");
});

test("no allowlist and no header means nobody can decide", () => {
  assert.equal(pickViewer({ users: [], headerMode: false, cookieValue: "David Wood" }), null);
});

test("displayPerson turns a known Slack id into a name", () => {
  assert.equal(displayPerson("U08V7ULPH1N", USERS), "David Wood");
  assert.equal(displayPerson("Aisha", USERS), "Aisha");
  assert.equal(displayPerson("U0UNKNOWN", USERS), "U0UNKNOWN");
  assert.equal(displayPerson(null, USERS), "");
});

test("aliasesFor lists every name a person's decisions are recorded under", () => {
  assert.deepEqual(aliasesFor("David Wood", USERS), ["David Wood", "U08V7ULPH1N"]);
  assert.deepEqual(aliasesFor("Aisha", USERS), ["Aisha"]);
  assert.deepEqual(aliasesFor("Someone From A Header", USERS), ["Someone From A Header"]);
});
