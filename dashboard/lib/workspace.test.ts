import { test } from "node:test";
import assert from "node:assert/strict";
import {
  actionsFor,
  approveLabel,
  changeCounts,
  changeTone,
  changeWord,
  checklistProgress,
  decidedLine,
  expectedDefault,
  DISCOVERY_TASKS,
  fitTone,
  latestSteps,
  locked,
  money,
  openStep,
  parseJson,
  openChangesReason,
  permissions,
  ratingTone,
  RECOMMENDATIONS,
  REQUIREMENT_ROWS,
  reviewLine,
  REVIEWERS,
  stageStates,
  stateTone,
  stateWord,
  STEPS,
  stepTitle,
  tagTone,
  taskLine,
  taskWord,
  type ChangeRow,
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
  assert.deepEqual(actionsFor(row("summary"), owner), { approve: true, askChanges: true, noGo: true, gate: false, retry: false, raiseCap: false, submit: false });
  assert.deepEqual(actionsFor(row("outline"), owner), { approve: true, askChanges: true, noGo: false, gate: false, retry: false, raiseCap: false, submit: false });
  assert.deepEqual(actionsFor(row("go_no_go"), owner), { approve: false, askChanges: true, noGo: false, gate: true, retry: false, raiseCap: false, submit: false });
  assert.deepEqual(actionsFor(row("submit"), owner), { approve: false, askChanges: false, noGo: false, gate: false, retry: false, raiseCap: false, submit: true });
  assert.deepEqual(actionsFor(row("draft", { state: "failed" }), owner), { approve: false, askChanges: false, noGo: false, gate: false, retry: true, raiseCap: false, submit: false });
  assert.deepEqual(actionsFor(row("draft", { state: "blocked" }), owner), { approve: false, askChanges: false, noGo: false, gate: false, retry: false, raiseCap: true, submit: false });
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

test("Discovery's eight tasks read with their states and a progress line (PW6)", () => {
  assert.equal(DISCOVERY_TASKS.length, 8);
  assert.equal(DISCOVERY_TASKS[0].id, "call_page");
  assert.equal(taskLine({ call_page: "done", attachments: "working", summary: "done", key_facts: "for_owner" }), "2 of 8 done, 1 working, 1 for you");
  assert.equal(taskLine({}), "0 of 8 done");
  assert.equal(taskWord("for_owner"), "for you");
  assert.equal(taskWord(undefined), "waiting");
});

test("the screens' badges and labels: alignment tags, the fit rating, the recommendation", () => {
  assert.deepEqual(["fits", "past work", "depends", "risk", "needs", "no clash"].map(tagTone), ["good", "good", "warn", "warn", "warn", "good"]);
  assert.deepEqual(["Strong fit", "Moderate fit", "Stretch fit", "Poor fit", "odd"].map(fitTone), ["good", "warn", "warn", "conflict", "grey"]);
  assert.equal(RECOMMENDATIONS.go_with_conditions, "Go with conditions");
  assert.deepEqual(REQUIREMENT_ROWS.map(([key]) => key), ["volumes", "page_limit", "evaluation", "eligibility", "keywords"]);
  assert.equal(approveLabel("summary"), "Continue to Alignment");
  assert.equal(approveLabel("draft"), "Approve and continue");
});

test("approving the Outline locks the direction and the past work (PW8, PW11)", () => {
  assert.equal(locked([row("outline", { state: "ready" })]), false);
  assert.equal(locked([row("outline", { state: "approved" })]), true);
  assert.equal(locked([row("outline", { id: 1, state: "approved" }), row("outline", { id: 2, attempt: 2, state: "queued" })]), true);
  assert.equal(locked([row("alignment")]), false);
});

function change(state: string, over: Partial<ChangeRow> = {}): ChangeRow {
  return {
    id: 1, step_id: 9, reviewer: "evaluator_1", section: "1. Technical approach", before_text: "now", after_text: "then",
    reason: "Clearer", state, edited_text: null, decided_by: null, decided_at: null, created_at: "2026-10-28T15:00:00Z", ...over,
  };
}

test("the three reviewers in order: two evaluators who rate the criteria, then leadership, who does not (PW12, PW25)", () => {
  assert.deepEqual(REVIEWERS.map((r) => [r.code, r.name, r.rates]), [
    ["evaluator_1", "External evaluator", true], ["evaluator_2", "Second evaluator", true], ["leadership", "Velocity leadership", false]]);
});

test("ratings in words read in tones; a scale of the call's own stays grey (PW25)", () => {
  assert.deepEqual(["Outstanding", "Good", "Acceptable", "Marginal", "Unacceptable", "good", "Satisfactory", ""].map(ratingTone),
    ["good", "good", "grey", "warn", "conflict", "good", "grey", "grey"]);
});

test("changes are counted by decision, and Reviews waits until every change is decided (PW12)", () => {
  const counts = changeCounts([change("proposed"), change("accepted"), change("edited"), change("rejected"), change("proposed")]);
  assert.deepEqual(counts, { total: 5, proposed: 2, accepted: 1, edited: 1, rejected: 1 });
  assert.equal(openChangesReason(counts.proposed), "Decide every change first: 2 still to decide.");
  assert.equal(openChangesReason(1), "Decide every change first: 1 still to decide.");
  assert.equal(openChangesReason(0), null);
  assert.equal(reviewLine(counts), "5 changes, 2 to decide");
  assert.equal(reviewLine(changeCounts([change("accepted"), change("edited"), change("rejected")])), "3 changes, 2 kept");
  assert.equal(reviewLine(changeCounts([change("accepted")])), "1 change, 1 kept");
  assert.equal(reviewLine(changeCounts([])), "No changes");
  assert.equal(decidedLine(changeCounts([change("accepted"), change("accepted"), change("rejected")])), "2 accepted, 1 rejected");
  assert.equal(decidedLine(changeCounts([])), "no changes");
});

test("each change's state in words and tones", () => {
  assert.deepEqual(["proposed", "accepted", "edited", "rejected"].map(changeWord), ["to decide", "accepted", "edited", "rejected"]);
  assert.deepEqual(["proposed", "accepted", "edited", "rejected"].map(changeTone), ["warn", "good", "good", "grey"]);
});


test("the result expected by date the Submit gate starts with: the pursuit's, then Discovery's, then 90 days after the deadline (P4)", () => {
  assert.deepEqual(expectedDefault({ pursuit: "2027-03-01", pursuitSource: "set at the Submit gate", discovery: { date: "2027-02-01", source: "Section 6" }, due: "2026-12-01" }),
    { date: "2027-03-01", note: "set at the Submit gate" });
  assert.deepEqual(expectedDefault({ pursuit: null, pursuitSource: null, discovery: { date: "2027-02-01", source: "Section 6: awards by 1 Feb" }, due: "2026-12-01" }),
    { date: "2027-02-01", note: "From Discovery: Section 6: awards by 1 Feb" });
  assert.deepEqual(expectedDefault({ pursuit: null, pursuitSource: null, discovery: null, due: "2026-12-01T17:00:00-05:00" }),
    { date: "2027-03-01", note: "About 90 days after the deadline. Change it if the solicitation says otherwise." });
  assert.deepEqual(expectedDefault({ pursuit: null, pursuitSource: null, discovery: null, due: "30 OCT 2026 : 21:59 MDT" }),
    { date: "", note: "The deadline does not give a date to count from; set one." });
});
