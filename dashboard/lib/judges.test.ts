import { test } from "node:test";
import assert from "node:assert/strict";
import { agreementText, judgesConflict, judgesDisagree, pickJudgeFilter, verdictsFor, type Judgment } from "./judges.ts";

const claude: Judgment = { judge: "claude", model: "claude-haiku-5-5", verdict: "yes", reasoning: "Fits.", rated_at: "t1" };
const grok: Judgment = { judge: "grok", model: "grok-4.7", verdict: "no", reasoning: "Hardware.", rated_at: "t2" };

test("verdictsFor pairs each judge's newest judgment", () => {
  const v = verdictsFor([grok, claude], "yes", "Fits.");
  assert.equal(v.claude?.verdict, "yes");
  assert.equal(v.grok?.verdict, "no");
});

test("verdictsFor falls back to the review's own verdict for Claude, and leaves Grok empty", () => {
  const v = verdictsFor(undefined, "maybe", "Unclear.");
  assert.deepEqual([v.claude?.verdict, v.claude?.reasoning, v.grok], ["maybe", "Unclear.", null]);
  assert.equal(verdictsFor([], null, null).claude, null);
});

test("judgesDisagree only when both judged and their verdicts differ", () => {
  assert.equal(judgesDisagree(verdictsFor([claude, grok], "yes", "")), true);
  assert.equal(judgesDisagree(verdictsFor([claude, { ...grok, verdict: "yes" }], "yes", "")), false);
  assert.equal(judgesDisagree(verdictsFor([claude], "yes", "")), false);
});

test("judgesConflict only when one judge says yes and the other no", () => {
  assert.equal(judgesConflict(verdictsFor([claude, grok], "yes", "")), true);
  assert.equal(judgesConflict(verdictsFor([claude, { ...grok, verdict: "maybe" }], "yes", "")), false);
  assert.equal(judgesConflict(verdictsFor([claude], "yes", "")), false);
});

test("agreementText states the rate, or nothing before both have judged", () => {
  assert.equal(agreementText(60, 45), "Claude and Grok agree on 45 of 60 calls (75%).");
  assert.equal(agreementText(1, 1), "Claude and Grok agree on 1 of 1 call (100%).");
  assert.equal(agreementText(0, 0), "");
});

test("pickJudgeFilter reads agree or disagree", () => {
  assert.equal(pickJudgeFilter("disagree"), "disagree");
  assert.equal(pickJudgeFilter("agree"), "agree");
  assert.equal(pickJudgeFilter("other"), "");
  assert.equal(pickJudgeFilter(undefined), "");
});
