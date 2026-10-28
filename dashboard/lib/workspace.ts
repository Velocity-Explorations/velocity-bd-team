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
    purpose: "Claude gathers everything about the call before anyone reads it: the page, every attachment, our past work and the team's record." },
  { name: "summary", label: "Opportunity summary", number: 2, stage: "qualify",
    purpose: "A two-minute read so you can decide whether the call is worth an alignment check." },
  { name: "alignment", label: "Alignment", number: 3, stage: "qualify",
    purpose: "How well the call fits Velocity, and the angle Claude proposes, so the requirements step reads the call the way you mean to answer it." },
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
    purpose: "Reviewers read the draft as evaluators and as Velocity's leadership, and the draft is revised before the final checks." },
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
  const none = { approve: false, askChanges: false, noGo: false, gate: false, retry: false, raiseCap: false };
  if (!r || !opts.decide || opts.pursuitState !== "working") return none;
  if (r.state === "ready") {
    return {
      ...none,
      approve: r.step !== "go_no_go" && r.step !== "submit",
      askChanges: r.step !== "submit",
      noGo: NO_GO_STEPS.includes(r.step),
      gate: r.step === "go_no_go",
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
