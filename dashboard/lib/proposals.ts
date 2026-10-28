// The Proposals section (P1 to P5, PRO-575): which view a pursued, drafting or submitted call belongs
// to, why a call cannot be drafted, the workspace's step names, days waiting, the result expected by
// date, and the five view cards. No imports, so `node --test` can load it directly.

export type ProposalView = "closing" | "to-draft" | "drafting" | "submitted" | "results";

/** A call with its pursuit, if it has one, and the state of the pursuit's current step. */
export type ProposalCall = {
  id: string;
  portal: string;
  title: string | null;
  url: string | null;
  type: string | null;
  department: string | null;
  naics_code: string | null;
  set_aside: string | null;
  due_date: string | null;
  days_left: number | null;
  default_result_by: string | null;
  extra: string | null;
  ai_verdict: string | null;
  ai_reasoning: string | null;
  human_status: string | null;
  human_by: string | null;
  human_at: string | null;
  pursuit_id: number | null;
  owner: string | null;
  pursuit_state: string | null;
  current_step: string | null;
  step_state: string | null;
  drive_folder_id: string | null;
  submitted_at: string | null;
  submitted_by: string | null;
  confirmation_number: string | null;
  result_expected_by: string | null;
  result_expected_source: string | null;
  result: string | null;
  result_at: string | null;
};

/** Days ahead that make a pursued or drafting call Closing in 14 days. */
export const CLOSING_DAYS = 14;

function extraFlags(extra: string | null): Record<string, unknown> {
  if (!extra) return {};
  try {
    const data: unknown = JSON.parse(extra);
    return data && typeof data === "object" && !Array.isArray(data) ? (data as Record<string, unknown>) : {};
  } catch {
    return {};
  }
}

/** Why a pursued call cannot be drafted, or null when it can (P2). */
export function draftBlock(row: Pick<ProposalCall, "extra">): "closed" | "needs the solicitation first" | null {
  const flags = extraFlags(row.extra);
  if (Object.entries(flags).some(([key, value]) => key.endsWith("_closed") && value === true)) return "closed";
  if (flags.nstxl_members_only === true) return "needs the solicitation first";
  return null;
}

const byDue = (a: ProposalCall, b: ProposalCall) => (a.days_left ?? Number.MAX_SAFE_INTEGER) - (b.days_left ?? Number.MAX_SAFE_INTEGER);

function submittedAt(row: ProposalCall): string {
  return row.submitted_at ?? row.human_at ?? "";
}

/**
 * The views each call belongs to: To draft (pursued, no pursuit, deadline not passed), Drafting (a
 * pursuit being worked), Closing in 14 days (either of those closing within 14 days), Submitted and
 * waiting (submitted, no result yet) and Results (a result recorded here). Each in its view's order.
 */
export function sortIntoViews(rows: ProposalCall[]): Record<ProposalView, ProposalCall[]> {
  const toDraft = rows.filter((r) => r.human_status === "pursue" && r.pursuit_id === null && (r.days_left === null || r.days_left >= 0)).sort(byDue);
  const drafting = rows.filter((r) => r.pursuit_state === "working").sort(byDue);
  const closing = [...toDraft, ...drafting]
    .filter((r) => r.days_left !== null && r.days_left >= 0 && r.days_left <= CLOSING_DAYS)
    .sort(byDue);
  const submitted = rows
    .filter((r) => (r.human_status === "submitted" || r.pursuit_state === "submitted") && !r.result)
    .sort((a, b) => submittedAt(a).localeCompare(submittedAt(b)));
  const results = rows.filter((r) => Boolean(r.result)).sort((a, b) => (b.result_at ?? "").localeCompare(a.result_at ?? ""));
  return { closing, "to-draft": toDraft, drafting, submitted, results };
}

const STEP_NAMES: Record<string, string> = {
  discovery: "Step 1, Discovery",
  summary: "Step 2, Opportunity summary",
  alignment: "Step 3, Alignment",
  requirements: "Step 4, Requirements and checklist",
  go_no_go: "Go or no-go gate",
  outline: "Step 5, Outline",
  draft: "Step 6, First draft",
  compliance: "Step 7, Compliance check",
  reviews: "Step 8, Reviews",
  final: "Step 9, Final checks",
  submit: "Submit gate",
};

/** A workspace step as the step list numbers it (PW3). */
export function stepLabel(step: string | null): string {
  return (step && STEP_NAMES[step]) || step || "";
}

/** A step's state in words (PW2, P3). */
export function stepStateWords(state: string | null): string {
  switch (state) {
    case "queued":
      return "waiting";
    case "ready":
      return "ready for the owner";
    case "blocked":
      return "budget reached";
    case "approved":
      return "done";
    default:
      return state ?? "";
  }
}

/** Whole days since the call was submitted. */
export function waitingDays(row: ProposalCall, now: Date): number {
  const at = submittedAt(row);
  if (!at) return 0;
  return Math.max(0, Math.floor((now.getTime() - new Date(at).getTime()) / (24 * 3600 * 1000)));
}

/**
 * When the result is expected (P4): the date Discovery found in the call, with where; else 90 days
 * after the deadline. Overdue once that date has passed.
 */
export function resultExpected(row: ProposalCall, today: string): { date: string | null; source: string; overdue: boolean } {
  const date = row.result_expected_by ?? row.default_result_by;
  const source = row.result_expected_source ?? (date ? "default, 90 days after the deadline" : "no deadline to count from");
  return { date, source, overdue: date !== null && date < today };
}

type Card = { key: string; label: string; count: number; description: string; href: string; current: boolean; needsYou: boolean };

const PATHS: Record<ProposalView, [string, string | null]> = {
  closing: ["/proposals", "closing"],
  "to-draft": ["/proposals", null],
  drafting: ["/proposals", "drafting"],
  submitted: ["/proposals/submitted", null],
  results: ["/proposals/results", null],
};

function href(view: ProposalView, params: Record<string, string | readonly string[]>): string {
  const [path, name] = PATHS[view];
  const query = new URLSearchParams();
  if (name) query.append("view", name);
  for (const key of ["portal", "tag", "state"]) {
    const value = params[key];
    for (const item of typeof value === "string" ? [value] : (value ?? [])) if (item) query.append(key, item);
  }
  const text = query.toString();
  return text ? `${path}?${text}` : path;
}

/** Proposals' five cards (P1): To draft carries the accent. Each keeps the bar's portal, tag and open or closed filters. */
export function proposalCards(input: {
  current: ProposalView;
  params: Record<string, string | readonly string[]>;
  counts: Record<ProposalView, number>;
  dueBy: string;
  longestWait: number;
  results: { won: number; lost: number };
}): Card[] {
  const { won, lost } = input.results;
  const decided = won + lost;
  const lines: Record<ProposalView, string> = {
    closing: `pursued, by ${input.dueBy}`,
    "to-draft": "pursued, no draft yet",
    drafting: "draft started, not submitted",
    submitted: input.counts.submitted ? `longest ${input.longestWait} ${input.longestWait === 1 ? "day" : "days"}` : "none waiting",
    results: decided ? `${won} won, ${lost} lost, ${((100 * won) / decided).toFixed(1)}% win rate` : "no results yet",
  };
  const labels: Record<ProposalView, string> = {
    closing: "Closing in 14 days",
    "to-draft": "To draft",
    drafting: "Drafting",
    submitted: "Submitted and waiting",
    results: "Results",
  };
  return (Object.keys(PATHS) as ProposalView[]).map((view) => ({
    key: view,
    label: labels[view],
    count: input.counts[view],
    description: lines[view],
    href: href(view, input.params),
    current: input.current === view,
    needsYou: view === "to-draft",
  }));
}
