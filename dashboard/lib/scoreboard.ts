// The judge scoreboard: how Claude and Grok compare with the people deciding. No imports, so
// `node --test` can load it directly. A verdict counts only if it was given before anyone
// decided the call: decided calls are among the examples in the judges' prompt, so a later
// verdict may have seen the answer.

export type DecisionRow = { call_id: string; decided_by: string; status: string; decided_at: string };
export type JudgmentRow = { call_id: string; judge: string; verdict: string; rated_at: string };
export type DecidedCall = { id: string; title: string | null; url: string | null; status: string; decided_at: string };
export type PersonRecord = { person: string; decided: number; withJudge: Record<string, { judged: number; matches: number }> };
export type Vote = { person: string; status: string; decided_at: string };

/** A decision as the verdict it agrees with: pursue and submitted are yes; not relevant and dismissed are no. */
export function decisionVerdict(status: string): "yes" | "no" | null {
  if (status === "pursue" || status === "submitted") return "yes";
  if (status === "not_relevant" || status === "dismissed") return "no";
  return null;
}

/** A judge's newest verdict on a call given before `before`, or null. Rows come oldest first. */
export function verdictBefore(judgments: JudgmentRow[], callId: string, judge: string, before: string): string | null {
  let found: string | null = null;
  for (const j of judgments) {
    if (j.call_id === callId && j.judge === judge && j.rated_at < before) found = j.verdict;
  }
  return found;
}

/** Each person's newest decision on each call. Rows come oldest first; Slack ids become names. */
function latestByPerson(decisions: DecisionRow[], displayName: (by: string) => string): Map<string, Map<string, DecisionRow>> {
  const byPerson = new Map<string, Map<string, DecisionRow>>();
  for (const d of decisions) {
    const person = displayName(d.decided_by);
    const calls = byPerson.get(person) ?? new Map<string, DecisionRow>();
    calls.set(d.call_id, d);
    byPerson.set(person, calls);
  }
  return byPerson;
}

/** When each call was first decided, by anyone. */
function firstDecided(decisions: DecisionRow[]): Map<string, string> {
  const first = new Map<string, string>();
  for (const d of decisions) {
    const seen = first.get(d.call_id);
    if (seen === undefined || d.decided_at < seen) first.set(d.call_id, d.decided_at);
  }
  return first;
}

/** For each person: calls decided, and how often each judge's verdict, given before the call was first decided, matched them. */
export function personRecords(
  decisions: DecisionRow[],
  judgments: JudgmentRow[],
  judges: readonly string[],
  displayName: (by: string) => string,
): PersonRecord[] {
  const first = firstDecided(decisions);
  const records: PersonRecord[] = [];
  for (const [person, calls] of latestByPerson(decisions, displayName)) {
    const withJudge = Object.fromEntries(judges.map((judge) => [judge, { judged: 0, matches: 0 }]));
    for (const d of calls.values()) {
      const wanted = decisionVerdict(d.status);
      for (const judge of judges) {
        const verdict = verdictBefore(judgments, d.call_id, judge, first.get(d.call_id) ?? d.decided_at);
        if (verdict === null || wanted === null) continue;
        withJudge[judge].judged += 1;
        if (verdict === wanted) withJudge[judge].matches += 1;
      }
    }
    records.push({ person, decided: calls.size, withJudge });
  }
  return records.sort((a, b) => a.person.localeCompare(b.person));
}

/** Each call's latest decision from each person, oldest first. */
export function votesByCall(decisions: DecisionRow[], displayName: (by: string) => string): Map<string, Vote[]> {
  const latest = new Map<string, Map<string, Vote>>();
  for (const d of decisions) {
    const people = latest.get(d.call_id) ?? new Map<string, Vote>();
    const person = displayName(d.decided_by);
    people.set(person, { person, status: d.status, decided_at: d.decided_at });
    latest.set(d.call_id, people);
  }
  const byCall = new Map<string, Vote[]>();
  for (const [callId, people] of latest) {
    byCall.set(callId, [...people.values()].sort((a, b) => a.decided_at.localeCompare(b.decided_at)));
  }
  return byCall;
}

/** True when one person's latest decision on a call is a yes and another's a no. */
export function peopleSplit(votes: Vote[]): boolean {
  const said = new Set(votes.map((v) => decisionVerdict(v.status)));
  return said.has("yes") && said.has("no");
}

/** Each pair of people: the calls both decided, and on how many they agree (submitted counts as pursue). */
export function peopleAgreement(
  decisions: DecisionRow[],
  displayName: (by: string) => string,
): { a: string; b: string; shared: number; agree: number }[] {
  const byPerson = latestByPerson(decisions, displayName);
  const people = [...byPerson.keys()].sort();
  const pairs: { a: string; b: string; shared: number; agree: number }[] = [];
  for (let i = 0; i < people.length; i++) {
    for (let k = i + 1; k < people.length; k++) {
      const theirs = byPerson.get(people[k]) ?? new Map<string, DecisionRow>();
      let shared = 0;
      let agree = 0;
      for (const [callId, d] of byPerson.get(people[i]) ?? new Map<string, DecisionRow>()) {
        const other = theirs.get(callId);
        if (!other) continue;
        shared += 1;
        if (decisionVerdict(d.status) === decisionVerdict(other.status)) agree += 1;
      }
      if (shared) pairs.push({ a: people[i], b: people[k], shared, agree });
    }
  }
  return pairs;
}

/** Calls the team pursued that a judge had called no before the decision. */
export function judgedMisses(
  calls: DecidedCall[],
  judgments: JudgmentRow[],
  judges: readonly string[],
): { id: string; title: string | null; url: string | null; judge: string }[] {
  const misses: { id: string; title: string | null; url: string | null; judge: string }[] = [];
  for (const call of calls) {
    if (decisionVerdict(call.status) !== "yes") continue;
    for (const judge of judges) {
      if (verdictBefore(judgments, call.id, judge, call.decided_at) === "no") {
        misses.push({ id: call.id, title: call.title, url: call.url, judge });
      }
    }
  }
  return misses;
}
