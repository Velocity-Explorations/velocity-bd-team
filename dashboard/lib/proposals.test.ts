import { test } from "node:test";
import assert from "node:assert/strict";
import {
  draftBlock,
  proposalCards,
  resultExpected,
  sortIntoViews,
  stepLabel,
  stepStateWords,
  waitingDays,
  type ProposalCall,
} from "./proposals.ts";

function call(id: string, over: Partial<ProposalCall> = {}): ProposalCall {
  return {
    id, portal: "SAM.gov", title: id, url: null, type: null, department: null, naics_code: null, set_aside: null,
    due_date: "2026-11-10", days_left: 13, default_result_by: "2027-02-08", extra: null, ai_verdict: "yes", ai_reasoning: null,
    human_status: "pursue", human_by: "David Wood", human_at: "2026-10-20T10:00:00Z",
    pursuit_id: null, owner: null, pursuit_state: null, current_step: null, step_state: null, drive_folder_id: null,
    submitted_at: null, submitted_by: null, confirmation_number: null, result_expected_by: null, result_expected_source: null,
    result: null, result_at: null,
    ...over,
  };
}

const NOW = new Date("2026-10-28T12:00:00Z");

test("pursued, drafting and submitted calls fall into the five views (P1 to P5)", () => {
  const rows = [
    call("to-draft-soon"),
    call("to-draft-later", { days_left: 40 }),
    call("past-deadline", { days_left: -2 }),
    call("drafting", { pursuit_id: 1, pursuit_state: "working", current_step: "outline", step_state: "ready", days_left: 5 }),
    call("submitted", { human_status: "submitted", human_at: "2026-10-20T10:00:00Z" }),
    call("submitted-drafted", { human_status: "submitted", pursuit_id: 2, pursuit_state: "submitted", submitted_at: "2026-10-25T10:00:00Z" }),
    call("won", { human_status: "submitted", pursuit_id: 3, pursuit_state: "submitted", result: "won", result_at: "2026-10-27T10:00:00Z" }),
    call("not-relevant", { human_status: "not_relevant" }),
  ];
  const views = sortIntoViews(rows);
  assert.deepEqual(views["to-draft"].map((r) => r.id), ["to-draft-soon", "to-draft-later"]);
  assert.deepEqual(views.drafting.map((r) => r.id), ["drafting"]);
  assert.deepEqual(views.closing.map((r) => r.id), ["drafting", "to-draft-soon"]);
  assert.deepEqual(views.submitted.map((r) => r.id), ["submitted", "submitted-drafted"]);
  assert.deepEqual(views.results.map((r) => r.id), ["won"]);
});

test("a call that cannot be drafted says why (P2)", () => {
  assert.equal(draftBlock(call("a", { extra: JSON.stringify({ sam_closed: true }) })), "closed");
  assert.equal(draftBlock(call("b", { extra: JSON.stringify({ nstxl_members_only: true }) })), "needs the solicitation first");
  assert.equal(draftBlock(call("c")), null);
});

test("steps read as the workspace numbers them, and their states in words (P3, PW2, PW3)", () => {
  assert.equal(stepLabel("discovery"), "Step 1, Discovery");
  assert.equal(stepLabel("requirements"), "Step 4, Requirements and checklist");
  assert.equal(stepLabel("go_no_go"), "Go or no-go gate");
  assert.equal(stepLabel("outline"), "Step 5, Outline");
  assert.equal(stepLabel("final"), "Step 9, Final checks");
  assert.equal(stepLabel("submit"), "Submit gate");
  assert.equal(stepStateWords("ready"), "ready for the owner");
  assert.equal(stepStateWords("queued"), "waiting");
  assert.equal(stepStateWords("working"), "working");
  assert.equal(stepStateWords("failed"), "failed");
  assert.equal(stepStateWords("blocked"), "budget reached");
});

test("days waiting count from the submission, and the result is expected 90 days after the deadline unless found (P4)", () => {
  assert.equal(waitingDays(call("a", { human_status: "submitted", human_at: "2026-10-20T10:00:00Z" }), NOW), 8);
  assert.equal(waitingDays(call("b", { submitted_at: "2026-10-27T13:00:00Z", human_at: "2026-10-01T00:00:00Z" }), NOW), 0);
  assert.deepEqual(resultExpected(call("c"), "2026-10-28"), { date: "2027-02-08", source: "default, 90 days after the deadline", overdue: false });
  assert.deepEqual(
    resultExpected(call("d", { result_expected_by: "2026-10-01", result_expected_source: "Section 6: awards by 1 Oct" }), "2026-10-28"),
    { date: "2026-10-01", source: "Section 6: awards by 1 Oct", overdue: true },
  );
  assert.deepEqual(resultExpected(call("e", { default_result_by: null }), "2026-10-28"), { date: null, source: "no deadline to count from", overdue: false });
});

test("Proposals has five cards, To draft in the accent, each keeping the bar's filters", () => {
  const cards = proposalCards({
    current: "submitted",
    params: { portal: ["NSTXL"], state: "open", sort: "due" },
    counts: { closing: 0, "to-draft": 0, drafting: 1, submitted: 2, results: 2 },
    dueBy: "8 Nov",
    longestWait: 1,
    results: { won: 1, lost: 1 },
  });
  assert.deepEqual(
    cards.map((c) => [c.label, c.href, c.count, c.description, c.current, c.needsYou]),
    [
      ["Closing in 14 days", "/proposals?view=closing&portal=NSTXL&state=open", 0, "pursued, by 8 Nov", false, false],
      ["To draft", "/proposals?portal=NSTXL&state=open", 0, "pursued, no draft yet", false, true],
      ["Drafting", "/proposals?view=drafting&portal=NSTXL&state=open", 1, "draft started, not submitted", false, false],
      ["Submitted and waiting", "/proposals/submitted?portal=NSTXL&state=open", 2, "longest 1 day", true, false],
      ["Results", "/proposals/results?portal=NSTXL&state=open", 2, "1 won, 1 lost, 50.0% win rate", false, false],
    ],
  );
  const empty = proposalCards({
    current: "to-draft", params: {}, counts: { closing: 0, "to-draft": 0, drafting: 0, submitted: 0, results: 0 },
    dueBy: "8 Nov", longestWait: 0, results: { won: 0, lost: 0 },
  });
  assert.deepEqual(empty.map((c) => c.description).slice(3), ["none waiting", "no results yet"]);
});
