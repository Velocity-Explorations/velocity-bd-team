import assert from "node:assert/strict";
import { test } from "node:test";
import { fitBadge, fitReasons, rankReason, whyThisScore } from "./fit.ts";

test("the fit badge gives the score and band, toned by band, with the reasons on hover", () => {
  assert.deepEqual(fitBadge({ fit_score: 88, fit_band: "strong", fit_why: '["Primary focus Software: Core","Customer USSF: Core"]' }),
    { text: "88 strong", tone: "good", why: "Primary focus Software: Core; Customer USSF: Core" });
  assert.equal(fitBadge({ fit_score: 60, fit_band: "possible", fit_why: "[]" })?.tone, "warn");
  assert.equal(fitBadge({ fit_score: 40, fit_band: "weak", fit_why: "[]" })?.tone, "grey");
});

test("a call ruled out says so without a score", () => {
  assert.deepEqual(fitBadge({ fit_score: 0, fit_band: "ruled out", fit_why: '["Ruled out: primary focus Services is rated Never"]' }),
    { text: "ruled out", tone: "bad", why: "Ruled out: primary focus Services is rated Never" });
});

test("a call with no score has no badge", () => {
  assert.equal(fitBadge({ fit_score: null, fit_band: null, fit_why: null }), null);
  assert.equal(fitBadge({}), null);
});

test("reasons that cannot be read give none", () => {
  assert.deepEqual(fitReasons("not json"), []);
  assert.deepEqual(fitReasons('{"a":1}'), []);
  assert.deepEqual(fitReasons(null), []);
});

// ------------------------------------------------------------------ Why this score (Task 4, 18 Nov 2026)

test("why a call scored what it did: the score and band, each part the scoring rated, and the keywords the filter matched", () => {
  const why = whyThisScore({
    fit_score: 89, fit_band: "strong",
    fit_why: JSON.stringify(["Primary focus Software: Core", "Type RFI: Good", "Customer USAF: Core", "Keyword communications: Core"]),
    matched_keywords: JSON.stringify(["information", "communications", "information"]),
  });
  assert.deepEqual(why, {
    headline: "Fit 89, strong",
    parts: ["Primary focus Software: Core", "Type RFI: Good", "Customer USAF: Core", "Keyword communications: Core"],
    matched: ["information", "communications"],
  });
});

test("a ruled out call and a call not scored yet say so", () => {
  assert.equal(whyThisScore({ fit_score: 0, fit_band: "ruled out", fit_why: JSON.stringify(["Ruled out: primary focus Hardware"]) }).headline,
    "Ruled out");
  const none = whyThisScore({ fit_score: null, fit_band: null, fit_why: null, matched_keywords: null });
  assert.equal(none.headline, "No fit score yet: no judge has named the call's primary focus");
  assert.deepEqual(none.parts, []);
  assert.deepEqual(none.matched, []);
});

test("the Top 10's ranking line follows its rule: the judges' yeses, then closing within 60 days, then the fit score", () => {
  assert.equal(rankReason({ claude: "yes", grok: "yes", daysLeft: 12, score: 89 }),
    "Yes from both judges; closes in 12 days, within the 60 days that rank first; then its fit score, 89.");
  assert.equal(rankReason({ claude: "yes", grok: "maybe", daysLeft: 90, score: 71 }),
    "Yes from one judge (Claude); closes in 90 days, after the calls that close within 60; then its fit score, 71.");
  assert.equal(rankReason({ claude: "maybe", grok: "yes", daysLeft: null, score: null }),
    "Yes from one judge (Grok); no deadline, so after the calls that close within 60 days; then its fit score, none yet.");
  assert.equal(rankReason({ claude: "maybe", grok: "maybe", daysLeft: 0, score: 40 }),
    "No yes from either judge; closes today, within the 60 days that rank first; then its fit score, 40.");
  assert.equal(rankReason({ claude: "yes", grok: null, daysLeft: -2, score: 69 }),
    "Yes from one judge (Claude); it closed 2 days ago, after the brief ranked it; then its fit score, 69.");
});
