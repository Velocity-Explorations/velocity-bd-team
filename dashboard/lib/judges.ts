// How Claude and Grok each judged a call (the judgments table, migration 003). No imports,
// so `node --test` can load it directly.

export type Judgment = { judge: string; model: string; verdict: string; reasoning: string | null; rated_at: string };
export type Verdicts = { claude: Judgment | null; grok: Judgment | null };
export type JudgeFilter = "agree" | "disagree" | "";

/** The judges in display order. */
export const JUDGES = [
  { key: "claude", label: "Claude" },
  { key: "grok", label: "Grok" },
] as const;

/**
 * Each judge's newest judgment on one call. Calls reviewed before migration 003 have no Claude
 * row yet, so Claude falls back to the review's own verdict, the one that decides what is posted.
 */
export function verdictsFor(judgments: Judgment[] | undefined, reviewVerdict: string | null, reviewReason: string | null): Verdicts {
  const pick = (judge: string) => (judgments ?? []).find((j) => j.judge === judge) ?? null;
  const claude = pick("claude")
    ?? (reviewVerdict ? { judge: "claude", model: "review", verdict: reviewVerdict, reasoning: reviewReason, rated_at: "" } : null);
  return { claude, grok: pick("grok") };
}

/** True only when both judges rated the call and their verdicts differ. */
export function judgesDisagree(v: Verdicts): boolean {
  return Boolean(v.claude && v.grok && v.claude.verdict !== v.grok.verdict);
}

/** True when one judge said yes and the other no, the disagreement that matters most. */
export function judgesConflict(v: Verdicts): boolean {
  const pair = [v.claude?.verdict, v.grok?.verdict].sort().join(" ");
  return pair === "no yes";
}

/** "Claude and Grok agree on 45 of 60 calls (75%).", or "" before both have judged a call. */
export function agreementText(both: number, agree: number): string {
  if (!both) return "";
  return `Claude and Grok agree on ${agree} of ${both} call${both === 1 ? "" : "s"} (${Math.round((100 * agree) / both)}%).`;
}

export function pickJudgeFilter(raw: string | string[] | undefined): JudgeFilter {
  const value = Array.isArray(raw) ? raw[0] : raw;
  return value === "agree" || value === "disagree" ? value : "";
}
