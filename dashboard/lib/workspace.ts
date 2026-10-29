// The proposal workspace (PW1 to PW25, PRO-580): the steps in order with their stages and numbers, each
// step's state in words, what each step is for, which step is open, and who may do what. No imports, so
// `node --test` can load it directly.

export type StageName = "qualify" | "plan" | "draft" | "review" | "finalize" | "submit";

/** One attempt at a step, as pursuit_steps holds it. */
export type StepRow = {
  id: number;
  pursuit_id: number;
  step: string;
  attempt: number;
  state: string;
  requested_by: string;
  request_note: string | null;
  summary: string | null;
  files: string | null;
  content: string | null;
  task_states: string | null;
  error: string | null;
  cost_usd: number;
  decision: string | null;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  queued_at: string;
  started_at: string | null;
  finished_at: string | null;
  updated_at: string;
};

export const STAGES: { name: StageName; label: string; doing: string }[] = [
  { name: "qualify", label: "Qualify", doing: "Qualifying" },
  { name: "plan", label: "Plan", doing: "Planning" },
  { name: "draft", label: "Draft", doing: "Drafting" },
  { name: "review", label: "Review", doing: "Reviewing" },
  { name: "finalize", label: "Finalize", doing: "Finalizing" },
  { name: "submit", label: "Submit", doing: "Submitting" },
];

/** The steps in order (PW3): nine numbered steps and two gates, each with what it is for (PW4). */
export const STEPS: { name: string; label: string; number: number | null; stage: StageName; purpose: string }[] = [
  { name: "discovery", label: "Discovery", number: 1, stage: "qualify",
    purpose: "The Writer gathers everything about the call before anyone reads it: the page, every attachment, our past work and the team's record." },
  { name: "summary", label: "Opportunity summary", number: 2, stage: "qualify",
    purpose: "A two-minute read so you can decide whether the call is worth an alignment check." },
  { name: "alignment", label: "Alignment", number: 3, stage: "qualify",
    purpose: "How well the call fits Velocity, and the angle the Writer proposes, so the requirements step reads the call the way you mean to answer it." },
  { name: "requirements", label: "Requirements and checklist", number: 4, stage: "qualify",
    purpose: "Everything the submission must contain and every rule it must meet, so nothing is found missing at the end." },
  { name: "go_no_go", label: "Go or no-go", number: null, stage: "qualify",
    purpose: "Steps 1 to 4 are approved. Decide whether Velocity writes this proposal." },
  { name: "outline", label: "Outline", number: 5, stage: "plan",
    purpose: "The sections, the criterion each answers, its share of the page limit, and the past work it draws on. The draft cites only what is listed." },
  { name: "draft", label: "First draft", number: 6, stage: "draft",
    purpose: "The full proposal, written section by section from the approved outline and the evidence list." },
  { name: "compliance", label: "Compliance check", number: 7, stage: "draft",
    purpose: "A mechanical check of the draft against the call's own words: keywords, functions, thresholds, phase scope and references." },
  { name: "reviews", label: "Reviews", number: 8, stage: "review",
    purpose: "The AI slop check runs on every new draft on its own. Then three reviewers read the draft in turn and suggest changes; you accept, reject or edit each, and Final checks puts the ones you keep into Draft v3." },
  { name: "final", label: "Final checks", number: 9, stage: "finalize",
    purpose: "The last checks before submitting: formatting, placeholders, the AI slop check and the checklist." },
  { name: "submit", label: "Submit", number: null, stage: "submit",
    purpose: "The owner submits on the portal, then records the confirmation number and when the result is expected." },
];

/** The steps whose card offers Stop here, no-go (PW4); the gate has its own No-go (PW10). */
export const NO_GO_STEPS = ["discovery", "summary", "alignment", "requirements"];

export function stepInfo(name: string): (typeof STEPS)[number] | undefined {
  return STEPS.find((s) => s.name === name);
}

/** The card's band: "Step 3 of 9 · Alignment", or "Gate · Go or no-go". */
export function stepTitle(name: string): string {
  const info = stepInfo(name);
  if (!info) return name;
  return info.number === null ? `Gate · ${info.label}` : `Step ${info.number} of 9 · ${info.label}`;
}

/** The newest attempt at each step. */
export function latestSteps(rows: StepRow[]): Map<string, StepRow> {
  const latest = new Map<string, StepRow>();
  for (const r of rows) {
    const seen = latest.get(r.step);
    if (!seen || r.id > seen.id) latest.set(r.step, r);
  }
  return latest;
}

/** A step's state in words (PW2, PW15, PW19). */
export function stateWord(r: StepRow | undefined): string {
  switch (r?.state) {
    case "working":
      return "working";
    case "ready":
      return "ready";
    case "approved":
      return "done";
    case "failed":
      return "failed";
    case "blocked":
      return "budget reached";
    case "stopped":
      return "stopped";
    case "skipped":
      return "skipped";
    default:
      return "waiting";
  }
}

export function stateTone(word: string): "good" | "info" | "warn" | "conflict" | "grey" {
  switch (word) {
    case "done":
      return "good";
    case "working":
      return "info";
    case "ready":
    case "budget reached":
      return "warn";
    case "failed":
      return "conflict";
    default:
      return "grey";
  }
}

/** The stage strip (PW1): stages before the current step's are done, its own is now, the rest next. */
export function stageStates(currentStep: string, pursuitState: string): Record<StageName, "done" | "now" | "next"> {
  const at = STAGES.findIndex((s) => s.name === stepInfo(currentStep)?.stage);
  const states = {} as Record<StageName, "done" | "now" | "next">;
  STAGES.forEach((s, i) => {
    states[s.name] = pursuitState === "submitted" || i < at ? "done" : i === at ? "now" : "next";
  });
  return states;
}

/** The step to open: the one asked for when the pursuit has reached it, else the current step. */
export function openStep(asked: string | undefined, latest: Map<string, StepRow>, current: string): string {
  return asked && latest.has(asked) ? asked : current;
}

/** The owner decides (PW17); the people working with them add material and tick items (PW24). */
export function permissions(viewer: string | null, owner: string, collaborators: string[]): { decide: boolean; contribute: boolean } {
  const decide = viewer !== null && viewer === owner;
  return { decide, contribute: decide || (viewer !== null && collaborators.includes(viewer)) };
}

/** What a step's card offers its owner, by the step and its state. Nothing while the pursuit is not worked. */
export function actionsFor(r: StepRow | undefined, opts: { pursuitState: string; decide: boolean }) {
  const none = { approve: false, askChanges: false, noGo: false, gate: false, retry: false, raiseCap: false, submit: false };
  if (!r || !opts.decide || opts.pursuitState !== "working") return none;
  if (r.state === "ready") {
    return {
      ...none,
      approve: r.step !== "go_no_go" && r.step !== "submit",
      askChanges: r.step !== "submit",
      noGo: NO_GO_STEPS.includes(r.step),
      gate: r.step === "go_no_go",
      submit: r.step === "submit",   // the Submit gate ends with Mark submitted (PW14)
    };
  }
  if ((r.state === "failed" || r.state === "blocked") && r.decision === null) {
    return r.state === "blocked" ? { ...none, raiseCap: true } : { ...none, retry: true };   // past the cap, only a higher cap helps
  }
  return none;
}

export function checklistProgress(items: { done: number | boolean }[]): { done: number; total: number } {
  return { done: items.filter((i) => Boolean(i.done)).length, total: items.length };
}

/** A JSON column, or the fallback when it is empty or does not parse. */
export function parseJson<T>(text: string | null | undefined, fallback: T): T {
  if (!text) return fallback;
  try {
    return JSON.parse(text) as T;
  } catch {
    return fallback;
  }
}

export function money(n: number): string {
  return `$${Number(n || 0).toFixed(2)}`;
}

// ------------------------------------------------------------------- each step's own screen (PRO-581)

/** Discovery's eight tasks (PW6), as the opportunity-assessment skill lists them. */
export const DISCOVERY_TASKS: { id: string; label: string; detail: string }[] = [
  { id: "call_page", label: "Re-check the call page", detail: "Still open, the deadline unchanged, amendments and posted questions and answers; the page saved as a PDF." },
  { id: "attachments", label: "Download every attachment", detail: "The solicitation or BAA, the statement of work, templates, forms and amendments." },
  { id: "parent_instructions", label: "Find the parent instructions", detail: "The BAA or the agency's own instructions the call points to, which hold page limits and format rules." },
  { id: "key_facts", label: "Pull out the key facts", detail: "Number, agency, point of contact, dates in our time zone, phase, funding, eligibility, the portal, and when results are announced." },
  { id: "past_work", label: "Compare with our past work", detail: "Starting from the past work chosen at Start the draft: similar topics, the same agency, wins, losses and debriefs." },
  { id: "clashes", label: "Check for clashes", detail: "An earlier submission to this call, the same call on another portal, and other pursued calls closing near the same date." },
  { id: "record", label: "Bring in the dashboard's record", detail: "Both judges' reasons, and the team's votes and notes." },
  { id: "summary", label: "Write the Discovery summary", detail: "What was found, what is missing and why, and questions for the point of contact." },
];

const TASK_WORDS: Record<string, string> = { done: "done", working: "working", for_owner: "for you", waiting: "waiting" };

export function taskWord(state: string | undefined): string {
  return (state && TASK_WORDS[state]) || "waiting";
}

/** "6 of 8 done, 2 for you": the progress line over Discovery's tasks. */
export function taskLine(tasks: Record<string, string>): string {
  const count = (state: string) => DISCOVERY_TASKS.filter((t) => tasks[t.id] === state).length;
  const parts = [`${count("done")} of ${DISCOVERY_TASKS.length} done`];
  if (count("working")) parts.push(`${count("working")} working`);
  if (count("for_owner")) parts.push(`${count("for_owner")} for you`);
  return parts.join(", ");
}

/** How each alignment point's tag reads (PW8): what fits in green, what depends or is at risk in amber. */
export function tagTone(tag: string): "good" | "warn" {
  return tag === "fits" || tag === "past work" || tag === "no clash" ? "good" : "warn";
}

export function fitTone(fit: string): "good" | "warn" | "conflict" | "grey" {
  switch (fit) {
    case "Strong fit":
      return "good";
    case "Moderate fit":
    case "Stretch fit":
      return "warn";
    case "Poor fit":
      return "conflict";
    default:
      return "grey";
  }
}

export const RECOMMENDATIONS: Record<string, string> = { go: "Go", go_with_conditions: "Go with conditions", no_go: "No-go" };

/** Requirements and checklist's summary rows (PW9). */
export const REQUIREMENT_ROWS: [string, string][] = [
  ["volumes", "Volumes"],
  ["page_limit", "Page limit and format"],
  ["evaluation", "Evaluation"],
  ["eligibility", "Eligibility"],
  ["keywords", "Keywords"],
];

/** The approve button's words: the summary continues to Alignment (PW7); the rest approve and continue. */
export function approveLabel(step: string): string {
  return step === "summary" ? "Continue to Alignment" : "Approve and continue";
}

/** Approving the Outline locks the direction and the past work (PW8, PW11): any approved attempt locks them. */
export function locked(rows: StepRow[]): boolean {
  return rows.some((r) => r.step === "outline" && r.state === "approved");
}

// ------------------------------------------------------------------- Reviews, change by change (phase 8b)

/** One reviewer's proposed change, as step_changes holds it (migration 008). */
export type ChangeRow = {
  id: number;
  step_id: number;
  reviewer: string;
  section: string | null;
  before_text: string | null;
  after_text: string | null;
  reason: string | null;
  state: string;
  edited_text: string | null;
  decided_by: string | null;
  decided_at: string | null;
  created_at: string;
};

/** The three reviewers in turn (PW12), by the code the worker stores; the evaluators rate the criteria (PW25). */
export const REVIEWERS: { code: string; name: string; note: string; rates: boolean }[] = [
  { code: "evaluator_1", name: "External evaluator", note: "Reads it as the agency's evaluator would, against the evaluation criteria.", rates: true },
  { code: "evaluator_2", name: "Second evaluator", note: "A second, independent read against the same criteria.", rates: true },
  { code: "leadership", name: "Velocity leadership", rates: false,
    note: "Overpromises, missed strengths, strategic fit, voice and resources; it does not rate the criteria." },
];

/** An evaluator's rating in words (PW25): Outstanding and Good in green, Marginal amber, Unacceptable red, the rest grey. */
export function ratingTone(rating: string): "good" | "warn" | "conflict" | "grey" {
  const word = rating.trim().toLowerCase().split(/[\s,;:(]/)[0];
  if (word === "outstanding" || word === "good") return "good";
  if (word === "marginal") return "warn";
  if (word === "unacceptable") return "conflict";
  return "grey";
}

export type ChangeCounts = { total: number; proposed: number; accepted: number; edited: number; rejected: number };

export function changeCounts(changes: { state: string }[]): ChangeCounts {
  const count = (state: string) => changes.filter((c) => c.state === state).length;
  return { total: changes.length, proposed: count("proposed"), accepted: count("accepted"), edited: count("edited"), rejected: count("rejected") };
}

/** Why Reviews cannot be approved yet (PW12): a change still to decide. */
export function openChangesReason(proposed: number): string | null {
  return proposed ? `Decide every change first: ${proposed} still to decide.` : null;
}

/** A reviewer's row: "14 changes, 3 to decide", or "14 changes, 13 kept" once decided. */
export function reviewLine(c: ChangeCounts): string {
  if (!c.total) return "No changes";
  const head = `${c.total} ${c.total === 1 ? "change" : "changes"}`;
  return c.proposed ? `${head}, ${c.proposed} to decide` : `${head}, ${c.accepted + c.edited} kept`;
}

/** What the owner decided, for the history when Reviews is approved: "30 accepted, 3 edited, 2 rejected". */
export function decidedLine(c: ChangeCounts): string {
  const parts = (["accepted", "edited", "rejected"] as const).filter((state) => c[state]).map((state) => `${c[state]} ${state}`);
  return parts.length ? parts.join(", ") : "no changes";
}

export function changeWord(state: string): string {
  return state === "proposed" ? "to decide" : state;
}

export function changeTone(state: string): "good" | "warn" | "grey" {
  return state === "proposed" ? "warn" : state === "rejected" ? "grey" : "good";
}

// ------------------------------------------------------------------- the Submit gate (phase 9b)

/** The result expected by date the Submit gate starts with (P4): the pursuit's, then Discovery's, then 90 days after the deadline. */
export function expectedDefault(input: {
  pursuit: string | null;
  pursuitSource: string | null;
  discovery: { date?: string | null; source?: string | null } | null;
  due: string | null;
}): { date: string; note: string } {
  if (input.pursuit) return { date: input.pursuit, note: input.pursuitSource ?? "" };
  if (input.discovery?.date) {
    return { date: input.discovery.date, note: `From Discovery${input.discovery.source ? `: ${input.discovery.source}` : ""}` };
  }
  const deadline = /^(\d{4})-(\d{2})-(\d{2})/.exec(input.due ?? "");
  if (!deadline) return { date: "", note: "The deadline does not give a date to count from; set one." };
  const date = new Date(Date.UTC(Number(deadline[1]), Number(deadline[2]) - 1, Number(deadline[3]) + 90)).toISOString().slice(0, 10);
  return { date, note: "About 90 days after the deadline. Change it if the solicitation says otherwise." };
}
