import { test } from "node:test";
import assert from "node:assert/strict";
import { isRequestChoice, KIND_LABELS, nextStep, previewText, REQUEST_KINDS, REQUEST_STATUSES } from "./requests.ts";

test("kinds and statuses are exactly the ledger's change_requests values", () => {
  assert.deepEqual([...REQUEST_KINDS], ["keyword_change", "rereview", "scan", "draft", "fault_report"]);
  assert.deepEqual([...REQUEST_STATUSES], ["proposed", "approved", "rejected", "applying", "applied", "failed"]);
  for (const kind of REQUEST_KINDS) assert.ok(KIND_LABELS[kind]);
});

test("isRequestChoice accepts only approve and reject", () => {
  assert.equal(isRequestChoice("approve"), true);
  assert.equal(isRequestChoice("reject"), true);
  assert.equal(isRequestChoice("applied"), false);
  assert.equal(isRequestChoice(null), false);
});

test("previewText reads the preview's text and survives bad JSON", () => {
  assert.equal(previewText('{"text": "Would keep 1 call.\\nNewly kept: A."}'), "Would keep 1 call.\nNewly kept: A.");
  assert.equal(previewText('{"other": 1}'), "");
  assert.equal(previewText("not json"), "");
  assert.equal(previewText(null), "");
});

test("nextStep says what happens to an approved request", () => {
  assert.equal(nextStep("scan", "approved", null), "Approved. The scan machine carries it out at its next pass (12:07 or 17:07).");
  assert.equal(nextStep("keyword_change", "approved", "Waiting: the scan machine is on branch dev."),
    "Waiting: the scan machine is on branch dev.");
  assert.equal(nextStep("draft", "approved", null), "Approved. The Writer starts the draft once it is built.");
  assert.equal(nextStep("scan", "applying", null), "Being carried out now.");
  assert.equal(nextStep("scan", "applied", "Run #20 completed."), "Run #20 completed.");
  assert.equal(nextStep("scan", "rejected", null), "");
});
