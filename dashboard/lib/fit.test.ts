import assert from "node:assert/strict";
import { test } from "node:test";
import { fitBadge, fitReasons } from "./fit.ts";

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
