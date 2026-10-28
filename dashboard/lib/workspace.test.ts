import { test } from "node:test";
import assert from "node:assert/strict";
import {
  actionsFor,
  checklistProgress,
  latestSteps,
  money,
  openStep,
  parseJson,
  permissions,
  stageStates,
  stateTone,
  stateWord,
  STEPS,
  stepTitle,
  type StepRow,
} from "./workspace.ts";

function row(step: string, over: Partial<StepRow> = {}): StepRow {
  return {
    id: 1, pursuit_id: 1, step, attempt: 1, state: "ready", requested_by: "David Wood", request_note: null, summary: null,
    files: null, content: null, task_states: null, error: null, cost_usd: 0, decision: null, decided_by: null,
    decided_at: null, decision_note: null, queued_at: "2026-10-28T15:00:00Z", started_at: null, finished_at: null,
    updated_at: "2026-10-28T15:00:00Z", ...over,
  };
}

test("the steps run in the workspace's order, numbered 1 to 9 with two gates (PW3)", () => {
  assert.deepEqual(STEPS.map((s) => [s.name, s.number, s.stage]), [
    ["discovery", 1, "qualify"], ["summary", 2, "qualify"], ["alignment", 3, "qualify"], ["requirements", 4, "qualify"],
    ["go_no_go", null, "qualify"], ["outline", 5, "plan"], ["draft", 6, "draft"], ["compliance", 7, "draft"],
    ["reviews", 8, "review"], ["final", 9, "finalize"], ["submit", null, "submit"],
  ]);
  assert.equal(stepTitle("alignment"), "Step 3 of 9 · Alignment");
  assert.equal(stepTitle("go_no_go"), "Gate · Go or no-go");
  assert.ok(STEPS.every((s) => s.purpose.length > 20));
});

test("the newest attempt at each step is the one shown", () => {
  const latest = latestSteps([row("discovery", { id: 1, state: "changes_asked" }), row("discovery", { id: 2, attempt: 2, state: "working" }),
    row("summary", { id: 3, state: "queued" })]);
  assert.equal(latest.get("discovery")?.id, 2);
  assert.equal(latest.get("summary")?.state, "queued");
});

test("each state reads in words with its tone (PW2, PW15, PW19)", () => {
  const words = ["queued", "working", "ready", "approved", "failed", "blocked", "stopped", "skipped"].map((state) => stateWord(row("draft", { state })));
  assert.deepEqual(words, ["waiting", "working", "ready", "done", "failed", "budget reached", "stopped", "skipped"]);
  assert.equal(stateWord(undefined), "waiting");
  assert.deepEqual(["waiting", "working", "ready", "done", "failed", "budget reached"].map(stateTone), ["grey", "info", "warn", "good", "conflict", "warn"]);
});

test("the stage strip marks done, now and next (PW1)", () => {
  assert.deepEqual(stageStates("alignment", "working"),
    { qualify: "now", plan: "next", draft: "next", review: "next", finalize: "next", submit: "next" });
  assert.deepEqual(stageStates("compliance", "working"),
    { qualify: "done", plan: "done", draft: "now", review: "next", finalize: "next", submit: "next" });
  assert.deepEqual(stageStates("submit", "submitted"),
    { qualify: "done", plan: "done", draft: "done", review: "done", finalize: "done", submit: "done" });
});

test("the step opened is the one asked for when it has been reached, else the current one", () => {
  const latest = latestSteps([row("discovery", { state: "approved" }), row("summary", { id: 2, state: "ready" })]);
  assert.equal(openStep("discovery", latest, "summary"), "discovery");
  assert.equal(openStep("outline", latest, "summary"), "summary");
  assert.equal(openStep(undefined, latest, "summary"), "summary");
});

test("only the owner decides; the people working with them contribute (PW17, PW24)", () => {
  assert.deepEqual(permissions("David Wood", "David Wood", ["Shaun Jones"]), { decide: true, contribute: true });
  assert.deepEqual(permissions("Shaun Jones", "David Wood", ["Shaun Jones"]), { decide: false, contribute: true });
  assert.deepEqual(permissions("Lisa Hall", "David Wood", ["Shaun Jones"]), { decide: false, contribute: false });
  assert.deepEqual(permissions(null, "David Wood", []), { decide: false, contribute: false });
});

test("a step's actions follow its state, the step and the owner (PW4, PW10, PW15, PW19)", () => {
  const owner = { pursuitState: "working", decide: true };
  assert.deepEqual(actionsFor(row("summary"), owner), { approve: true, askChanges: true, noGo: true, gate: false, retry: false, raiseCap: false });
  assert.deepEqual(actionsFor(row("outline"), owner), { approve: true, askChanges: true, noGo: false, gate: false, retry: false, raiseCap: false });
  assert.deepEqual(actionsFor(row("go_no_go"), owner), { approve: false, askChanges: true, noGo: false, gate: true, retry: false, raiseCap: false });
  assert.deepEqual(actionsFor(row("submit"), owner), { approve: false, askChanges: false, noGo: false, gate: false, retry: false, raiseCap: false });
  assert.deepEqual(actionsFor(row("draft", { state: "failed" }), owner), { approve: false, askChanges: false, noGo: false, gate: false, retry: true, raiseCap: false });
  assert.deepEqual(actionsFor(row("draft", { state: "blocked" }), owner), { approve: false, askChanges: false, noGo: false, gate: false, retry: false, raiseCap: true });
  assert.equal(actionsFor(row("draft", { state: "failed", decision: "retried" }), owner).retry, false);
  assert.equal(actionsFor(row("summary"), { pursuitState: "working", decide: false }).approve, false);
  assert.equal(actionsFor(row("summary"), { pursuitState: "closed", decide: true }).approve, false);
});

test("the checklist counts what is done, the JSON columns parse, and money reads in dollars", () => {
  assert.deepEqual(checklistProgress([{ done: 1 }, { done: 0 }, { done: true }]), { done: 2, total: 3 });
  assert.deepEqual(parseJson('{"a": 1}', {}), { a: 1 });
  assert.deepEqual(parseJson("not json", []), []);
  assert.deepEqual(parseJson(null, { none: true }), { none: true });
  assert.equal(money(0.4007), "$0.40");
  assert.equal(money(200), "$200.00");
});
