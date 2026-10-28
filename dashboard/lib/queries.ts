// Every query the dashboard runs. The SQL follows docs/LEDGER_SCHEMA.md; counts are cast to
// int and rates to float8 because Postgres returns bigint and numeric, which arrive as strings.

import { sql } from "./db";
import { CLOSED_PATTERN, portalOptions, type CallState, type PortalOption, type Sort } from "./filters";
import type { JudgeFilter, Judgment } from "./judges";
import type { TagOption, TagRow } from "./tags";
import { isoNow } from "./format";
import type { RequestChoice } from "./requests";
import type { DecidedCall, DecisionRow, JudgmentRow } from "./scoreboard";
import { escapeLike, noteLine } from "./text";
import { isDecision, planDecision, type Decision } from "./values";
import { DUE_SOON_DAYS, type CallView } from "./views";

// ------------------------------------------------------------------------------ calls

export type QueueRow = {
  id: string;
  portal: string;
  title: string | null;
  url: string | null;
  type: string | null;
  department: string | null;
  naics_code: string | null;
  set_aside: string | null;
  ai_verdict: string;
  ai_reasoning: string | null;
  due_date: string | null;
  match_tier: string | null;
  first_seen_at: string;
  extra: string | null;
  human_status: string | null;
};

/** The filter panel's choices (lib/filters.ts). No portals ticked means every portal; no tag, any tag. */
export type PanelFilters = { portals: string[]; state: CallState; sort: Sort; judges: JudgeFilter; tag: string };

type Db = ReturnType<typeof sql>;

/** The panel's portal and open-or-closed conditions, appended after a WHERE. */
function panelWhere(db: Db, f: PanelFilters) {
  return db`
    ${f.portals.length ? db`AND portal IN ${db(f.portals)}` : db``}
    ${f.state === "open" ? db`AND (extra IS NULL OR extra !~ ${CLOSED_PATTERN})` : db``}
    ${f.state === "closed" ? db`AND extra ~ ${CLOSED_PATTERN}` : db``}
    ${f.judges === "disagree" ? db`AND ${newestVerdict(db, "claude")} <> ${newestVerdict(db, "grok")}` : db``}
    ${f.judges === "agree" ? db`AND ${newestVerdict(db, "claude")} = ${newestVerdict(db, "grok")}` : db``}
    ${f.tag ? db`AND EXISTS (SELECT 1 FROM call_tags AS t WHERE t.call_id = calls.id AND t.tag = ${f.tag})` : db``}`;
}

/** One judge's newest verdict on the outer query's call (judgments table); NULL when it has not judged. */
function newestVerdict(db: Db, judge: string) {
  return db`(SELECT j.verdict FROM judgments AS j WHERE j.call_id = calls.id AND j.judge = ${judge} ORDER BY j.id DESC LIMIT 1)`;
}

/** due_date as a date, from either shape the portals write: "27 OCT 2026 : 21:59 MDT" or "2026-10-27". */
function dueDate(db: Db) {
  return db`CASE
      WHEN due_date ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}' THEN to_date(substring(due_date from 1 for 10), 'YYYY-MM-DD')
      WHEN due_date ~ '^[0-9]{1,2} [A-Za-z]{3} [0-9]{4}'
        THEN to_date(substring(due_date from '^[0-9]{1,2} [A-Za-z]{3} [0-9]{4}'), 'DD Mon YYYY')
    END`;
}

/**
 * The column a header sorts by (PRO-558), then newest first. Closing soonest puts upcoming deadlines
 * first, then undated calls, then past ones. Verdict, tier, decision and filter sort by rank: yes,
 * tight, pursue and kept come first. Under the disagree filter, calls where one judge said yes and
 * the other no come first whatever the sort.
 */
function panelOrder(db: Db, f: { sort: Sort; judges: JudgeFilter }) {
  const conflictsFirst = f.judges === "disagree"
    ? db`(${newestVerdict(db, "claude")} IN ('yes', 'no') AND ${newestVerdict(db, "grok")} IN ('yes', 'no')) IS NOT TRUE,`
    : db``;
  const dir = f.sort.dir === "desc" ? db`DESC` : db`ASC`;
  switch (f.sort.key) {
    case "due":
      return f.sort.dir === "asc"
        ? db`ORDER BY ${conflictsFirst} (${dueDate(db)} < CURRENT_DATE) IS TRUE, ${dueDate(db)} ASC NULLS LAST, first_seen_at DESC, id`
        : db`ORDER BY ${conflictsFirst} ${dueDate(db)} DESC NULLS LAST, first_seen_at DESC, id`;
    case "title":
      return db`ORDER BY ${conflictsFirst} lower(title) ${dir} NULLS LAST, first_seen_at DESC, id`;
    case "verdict":
      return db`ORDER BY ${conflictsFirst} CASE ai_verdict WHEN 'yes' THEN 0 WHEN 'maybe' THEN 1 WHEN 'no' THEN 2 ELSE 3 END ${dir},
                first_seen_at DESC, id`;
    case "tier":
      return db`ORDER BY ${conflictsFirst} CASE match_tier WHEN 'tight' THEN 0 WHEN 'broad' THEN 1 ELSE 2 END ${dir}, first_seen_at DESC, id`;
    case "decision":
      return db`ORDER BY ${conflictsFirst} CASE human_status WHEN 'pursue' THEN 0 WHEN 'submitted' THEN 1 WHEN 'not_relevant' THEN 2
                WHEN 'dismissed' THEN 3 ELSE 4 END ${dir}, first_seen_at DESC, id`;
    case "filter":
      return db`ORDER BY ${conflictsFirst} CASE filter_result WHEN 'kept' THEN 0 WHEN 'pending' THEN 1 WHEN 'rejected' THEN 2 ELSE 3 END ${dir},
                first_seen_at DESC, id`;
    default:
      return db`ORDER BY ${conflictsFirst} first_seen_at ${dir}, id`;
  }
}

/** True when a ledger table exists; a migration may not be applied to this database yet. */
async function hasTable(db: Db, name: string): Promise<boolean> {
  const [row] = await db<{ present: boolean }[]>`SELECT to_regclass(${name}::text) IS NOT NULL AS present`;
  return Boolean(row?.present);
}

/**
 * The calls waiting for a decision: rated yes or maybe and kept by the keyword filter. Per person
 * (`perPerson`, with the names one person's decisions are recorded under): the calls that person
 * has not decided. Otherwise: the calls nobody has decided.
 */
function waitingWhere(db: Db, perPerson: boolean, waitingFor: string[] | null) {
  return db`ai_verdict IN ('yes', 'maybe')
      AND filter_result = 'kept'
      AND ${perPerson
        ? db`NOT EXISTS (SELECT 1 FROM decisions AS d WHERE d.call_id = calls.id AND d.decided_by IN ${db(waitingFor ?? [])})`
        : db`human_status IS NULL`}`;
}

/** A deadline from today through the next DUE_SOON_DAYS days. */
function dueSoon(db: Db) {
  return db`${dueDate(db)} BETWEEN CURRENT_DATE AND CURRENT_DATE + ${DUE_SOON_DAYS}::int`;
}

/** The bar's filters alone (portals, tag, open or closed): what view card counts follow (VC2). */
export type BarFilters = Pick<PanelFilters, "portals" | "state" | "tag">;

function barOnly(f: BarFilters): PanelFilters {
  return { portals: f.portals, state: f.state, tag: f.tag, judges: "", sort: { key: "seen", dir: "desc" } };
}

/**
 * The triage backlog, newest first unless sorted otherwise. With `waitingFor` (the names one
 * person's decisions are recorded under, while everyone decides every call): the calls that
 * person has not decided. Otherwise, and before migration 004: the calls nobody has decided,
 * the "Triage backlog" query in LEDGER_SCHEMA.md. A call a later keyword change dropped leaves it.
 * The Due soon view keeps those closing within DUE_SOON_DAYS.
 */
export async function reviewQueue(
  f: PanelFilters & { verdict: string; tier: string; view?: CallView },
  waitingFor: string[] | null,
): Promise<{ rows: QueueRow[]; perPerson: boolean }> {
  const db = sql();
  const perPerson = Boolean(waitingFor?.length) && (await hasTable(db, "decisions"));
  const rows = await db<QueueRow[]>`
    SELECT id, portal, title, url, type, department, naics_code, set_aside, ai_verdict, ai_reasoning, due_date,
           match_tier, first_seen_at, extra, human_status
    FROM calls
    WHERE ${waitingWhere(db, perPerson, waitingFor)}
      ${f.view === "due-soon" ? db`AND ${dueSoon(db)}` : db``}
      ${f.verdict ? db`AND ai_verdict = ${f.verdict}` : db``}
      ${f.tier ? db`AND match_tier = ${f.tier}` : db``}
      ${panelWhere(db, f)}
    ${panelOrder(db, f)}
    LIMIT 500`;
  return { rows: [...rows], perPerson };
}

/** Needs review's and Due soon's counts under the bar's filters; the column filters do not narrow them. */
export async function queueCounts(f: BarFilters, waitingFor: string[] | null): Promise<{ waiting: number; dueSoon: number; yes: number }> {
  const db = sql();
  const perPerson = Boolean(waitingFor?.length) && (await hasTable(db, "decisions"));
  const [row] = await db<{ waiting: number; due_soon: number; yes: number }[]>`
    SELECT COUNT(*)::int AS waiting,
           COUNT(*) FILTER (WHERE ${dueSoon(db)})::int AS due_soon,
           COUNT(*) FILTER (WHERE ai_verdict = 'yes')::int AS yes
    FROM calls
    WHERE ${waitingWhere(db, perPerson, waitingFor)}
      ${panelWhere(db, barOnly(f))}`;
  return { waiting: row?.waiting ?? 0, dueSoon: row?.due_soon ?? 0, yes: row?.yes ?? 0 };
}

/** All calls' count under the bar's filters, for its card. */
export async function countCalls(f: BarFilters): Promise<number> {
  const db = sql();
  const [row] = await db<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM calls WHERE TRUE ${panelWhere(db, barOnly(f))}`;
  return row?.n ?? 0;
}

/** Pursued calls still open with no pursuit yet: Proposals to draft (P2). */
export async function countToDraft(): Promise<number> {
  const db = sql();
  const pursuits = await hasTable(db, "pursuits");
  const [row] = await db<{ n: number }[]>`
    SELECT COUNT(*)::int AS n FROM calls
    WHERE human_status = 'pursue' AND (extra IS NULL OR extra !~ ${CLOSED_PATTERN})
      ${pursuits ? db`AND NOT EXISTS (SELECT 1 FROM pursuits AS p WHERE p.call_id = calls.id)` : db``}`;
  return row?.n ?? 0;
}

/** Calls marked Submitted with no result recorded yet: Submitted and waiting (P4). */
export async function countSubmittedWaiting(): Promise<number> {
  const db = sql();
  const pursuits = await hasTable(db, "pursuits");
  const [row] = await db<{ n: number }[]>`
    SELECT COUNT(*)::int AS n FROM calls
    WHERE human_status = 'submitted'
      ${pursuits ? db`AND NOT EXISTS (SELECT 1 FROM pursuits AS p WHERE p.call_id = calls.id AND p.result IS NOT NULL)` : db``}`;
  return row?.n ?? 0;
}

/** Workspace steps ready for their owner, among these names (the viewer's), on pursuits being worked. */
export async function countStepsReadyFor(names: string[]): Promise<number> {
  if (names.length === 0) return 0;
  const db = sql();
  if (!(await hasTable(db, "pursuits"))) return 0;
  const [row] = await db<{ n: number }[]>`
    SELECT COUNT(*)::int AS n
    FROM pursuit_steps AS s JOIN pursuits AS p ON p.id = s.pursuit_id
    WHERE s.state = 'ready' AND p.state = 'working' AND p.owner IN ${db(names)}`;
  return row?.n ?? 0;
}

export type TopTenRow = {
  id: string;
  portal: string;
  title: string | null;
  url: string | null;
  due_date: string | null;
  days_left: number | null;
  description: string | null;
  ai_verdict: string | null;
  ai_reasoning: string | null;
  human_status: string | null;
  human_by: string | null;
};

/** Home's Top 10 rows for these calls, as the ledger has them now; the caller keeps the order. */
export async function topTenRows(ids: string[]): Promise<TopTenRow[]> {
  if (ids.length === 0) return [];
  const db = sql();
  const rows = await db<TopTenRow[]>`
    SELECT id, portal, title, url, due_date, (${dueDate(db)} - CURRENT_DATE)::int AS days_left, description,
           ai_verdict, ai_reasoning, human_status, human_by
    FROM calls WHERE id IN ${db(ids)}`;
  return [...rows];
}

/**
 * The live ranking Home shows before the first Monday brief (H2): open calls nobody has decided,
 * rated yes or maybe and kept, yes before maybe, then the nearest deadline, then the newest.
 */
export async function liveTopTen(): Promise<string[]> {
  const db = sql();
  const rows = await db<{ id: string }[]>`
    SELECT id FROM calls
    WHERE ${waitingWhere(db, false, null)}
      AND (extra IS NULL OR extra !~ ${CLOSED_PATTERN})
      AND (${dueDate(db)} >= CURRENT_DATE OR ${dueDate(db)} IS NULL)
    ORDER BY CASE ai_verdict WHEN 'yes' THEN 0 ELSE 1 END, ${dueDate(db)} ASC NULLS LAST, first_seen_at DESC, id
    LIMIT 10`;
  return rows.map((r) => r.id);
}

/** "New calls this week" from LEDGER_SCHEMA.md, as a count. */
export async function newThisWeek(): Promise<number> {
  const cutoff = isoNow(new Date(Date.now() - 7 * 24 * 3600 * 1000));
  const [row] = await sql()<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM calls WHERE first_seen_at >= ${cutoff}`;
  return row?.n ?? 0;
}

/** Every portal that has completed a real scan or has calls, with its number of stored calls (PRO-563). */
export async function portals(): Promise<PortalOption[]> {
  const [scanned, counts] = await Promise.all([
    sql()<{ portal: string }[]>`SELECT DISTINCT portal FROM runs WHERE portal IS NOT NULL AND dry_run = 0`,
    sql()<{ portal: string; calls: number }[]>`SELECT portal, COUNT(*)::int AS calls FROM calls WHERE portal IS NOT NULL GROUP BY portal`,
  ]);
  return portalOptions(scanned.map((r) => r.portal), [...counts]);
}

/**
 * Each judge's newest judgment on these calls, by call id. Empty when the judgments table is not
 * there yet (migration 003): the pages then show the review's verdict alone.
 */
export async function latestJudgments(callIds: string[]): Promise<Map<string, Judgment[]>> {
  const byCall = new Map<string, Judgment[]>();
  if (callIds.length === 0) return byCall;
  try {
    const db = sql();
    const found = await db<(Judgment & { call_id: string })[]>`
      SELECT DISTINCT ON (call_id, judge) call_id, judge, model, verdict, reasoning, rated_at
      FROM judgments
      WHERE call_id IN ${db(callIds)}
      ORDER BY call_id, judge, id DESC`;
    for (const { call_id, ...judgment } of found) {
      byCall.set(call_id, [...(byCall.get(call_id) ?? []), judgment]);
    }
  } catch {
    // judgments table missing: nothing to add
  }
  return byCall;
}

/** "Judge agreement" from LEDGER_SCHEMA.md: calls both judges rated, and how many verdicts match. */
export async function judgeAgreement(): Promise<{ both: number; agree: number } | null> {
  try {
    const [row] = await sql()<{ both_judged: number; agree: number }[]>`
      SELECT COUNT(*)::int AS both_judged,
             COALESCE(SUM(CASE WHEN c.verdict = g.verdict THEN 1 ELSE 0 END), 0)::int AS agree
      FROM judgments AS c
      JOIN judgments AS g ON g.call_id = c.call_id AND g.judge = 'grok'
      WHERE c.judge = 'claude'
        AND c.id = (SELECT MAX(id) FROM judgments WHERE call_id = c.call_id AND judge = 'claude')
        AND g.id = (SELECT MAX(id) FROM judgments WHERE call_id = g.call_id AND judge = 'grok')`;
    return { both: row?.both_judged ?? 0, agree: row?.agree ?? 0 };
  } catch {
    return null;   // judgments table missing (migration 003)
  }
}

export type CallFilters = PanelFilters & { filterResult: string; verdict: string; status: string; q: string };

export type CallRow = {
  id: string;
  portal: string;
  title: string | null;
  url: string | null;
  type: string | null;
  department: string | null;
  naics_code: string | null;
  set_aside: string | null;
  due_date: string | null;
  filter_result: string;
  filter_reason: string | null;
  match_tier: string | null;
  ai_verdict: string | null;
  ai_reasoning: string | null;
  human_status: string | null;
  human_by: string | null;
  human_at: string | null;
  human_notes: string | null;
  first_seen_at: string;
  extra: string | null;
};

export async function listCalls(f: CallFilters, limit = 200): Promise<{ rows: CallRow[]; total: number }> {
  const db = sql();
  const where = () => db`
    WHERE TRUE
      ${f.filterResult ? db`AND filter_result = ${f.filterResult}` : db``}
      ${f.verdict === "none" ? db`AND ai_verdict IS NULL` : f.verdict ? db`AND ai_verdict = ${f.verdict}` : db``}
      ${f.status === "none" ? db`AND human_status IS NULL` : f.status ? db`AND human_status = ${f.status}` : db``}
      ${f.q ? db`AND title ILIKE ${`%${escapeLike(f.q)}%`}` : db``}
      ${panelWhere(db, f)}`;
  const [count, rows] = await Promise.all([
    db<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM calls ${where()}`,
    db<CallRow[]>`
      SELECT id, portal, title, url, type, department, naics_code, set_aside, due_date, filter_result, filter_reason, match_tier,
             ai_verdict, ai_reasoning, human_status, human_by, human_at, human_notes, first_seen_at, extra
      FROM calls ${where()}
      ${panelOrder(db, f)}
      LIMIT ${limit}`,
  ]);
  return { rows: [...rows], total: count[0]?.n ?? 0 };
}

export type DecideResult =
  | { ok: true; title: string; plan: "decide" | "add" | "note"; callStatus: Decision | null }
  | { ok: false; reason: string };

/** The newest decision recorded under any of these names on a call, or null. */
async function latestDecisionBy(db: Db, callId: string, aliases: string[]): Promise<string | null> {
  if (aliases.length === 0) return null;
  const [row] = await db<{ status: string }[]>`
    SELECT status FROM decisions WHERE call_id = ${callId} AND decided_by IN ${db(aliases)} ORDER BY id DESC LIMIT 1`;
  return row?.status ?? null;
}

/**
 * The dashboard's one write, and since 2026-10-17 the only place decisions are made:
 * human_status, human_by, human_at, plus an optional note appended in append_note()'s
 * format, and a row in `decisions` (migration 004) so every person's decision is kept.
 * Choosing the decision a call already has, when it is someone else's, adds yours without
 * changing the call; so does any decision with `keepCallDecision` (the review queue while
 * everyone decides every call) once the call has one. Otherwise `expected` is the decision
 * the page showed; if the call changed since (another tab, another person), nothing is
 * written and the reason says what it is now. `aliases` are the names the person's earlier
 * decisions are recorded under.
 */
export async function decideCall(input: {
  id: string;
  status: Decision;
  expected: Decision | null;
  keepCallDecision: boolean;
  by: string;
  aliases: string[];
  note: string;
}): Promise<DecideResult> {
  const db = sql();
  const history = await hasTable(db, "decisions");
  const mine = history ? await latestDecisionBy(db, input.id, input.aliases) : null;
  const now = isoNow();
  const line = noteLine(now, input.by, input.note) || null;
  return db.begin(async (tx): Promise<DecideResult> => {
    const [call] = await tx<{ title: string | null; human_status: string | null; human_by: string | null }[]>`
      SELECT title, human_status, human_by FROM calls WHERE id = ${input.id} FOR UPDATE`;
    if (!call) return { ok: false, reason: "That call is no longer in the ledger." };
    const current = isDecision(call.human_status) ? call.human_status : null;
    const keep = input.keepCallDecision && history;
    if (current !== input.expected && !keep) {
      return {
        ok: false,
        reason: current
          ? `It was changed meanwhile to ${current} by ${call.human_by}. Nothing saved; reload and try again.`
          : "Its decision was cleared meanwhile. Nothing saved; reload and try again.",
      };
    }
    const plan = planDecision(current, input.status, input.note, history ? mine : current, keep);
    if (plan === "noop") return { ok: false, reason: "Nothing to save: choose a different decision or add a note." };
    await tx`
      UPDATE calls
      SET ${plan === "decide" ? tx`human_status = ${input.status}, human_by = ${input.by}, human_at = ${now},` : tx``}
          updated_at = ${now},
          human_notes = CASE
            WHEN ${line}::text IS NULL THEN human_notes
            ELSE COALESCE(NULLIF(human_notes, '') || chr(10), '') || ${line}::text
          END
      WHERE id = ${input.id}`;
    if (history && plan !== "note") {
      await tx`
        INSERT INTO decisions (call_id, decided_by, status, note, decided_at)
        VALUES (${input.id}, ${input.by}, ${input.status}, ${input.note.trim() || null}, ${now})`;
    }
    return { ok: true, title: call.title ?? input.id, plan, callStatus: plan === "decide" ? input.status : current };
  });
}

// ------------------------------------------------------------------ tags

/** Every tag on these calls, with who set it and its group and place in the list (call_tags and
 *  tag_list, migrations 006 and 007); empty before those tables exist. */
export async function tagsOn(callIds: string[]): Promise<TagRow[]> {
  if (callIds.length === 0) return [];
  try {
    const db = sql();
    const rows = await db<TagRow[]>`
      SELECT t.call_id, t.tag, t.source, l.tag_group, l.position
      FROM call_tags AS t LEFT JOIN tag_list AS l ON l.name = t.tag
      WHERE t.call_id IN ${db(callIds)}
      ORDER BY t.id`;
    return [...rows];
  } catch {
    return [];   // call_tags or tag_list missing
  }
}

/** The tag list, in order, for the Tag filter; empty before migration 007. */
export async function tagOptions(): Promise<TagOption[]> {
  try {
    const rows = await sql()<TagOption[]>`SELECT name, tag_group, covers FROM tag_list ORDER BY position`;
    return [...rows];
  } catch {
    return [];
  }
}

// ------------------------------------------------------------------ decisions, judges

/** Every decision on these calls, oldest first (migration 004); empty before that table exists. */
export async function decisionsOn(callIds: string[]): Promise<DecisionRow[]> {
  if (callIds.length === 0) return [];
  try {
    const db = sql();
    const rows = await db<DecisionRow[]>`
      SELECT call_id, decided_by, status, decided_at FROM decisions WHERE call_id IN ${db(callIds)} ORDER BY id`;
    return [...rows];
  } catch {
    return [];   // decisions table missing (migration 004)
  }
}

export type JudgeRecord = { judge: string; decided: number; matches: number; misses: number; false_alarms: number };

/** "Judge scoreboard" from LEDGER_SCHEMA.md, unchanged, wrapped only to cast its numbers. Null before migration 004. */
export async function judgeRecords(): Promise<JudgeRecord[] | null> {
  try {
    const rows = await sql()<JudgeRecord[]>`
      SELECT judge, decided::int AS decided, matches::int AS matches, misses::int AS misses,
             false_alarms::int AS false_alarms
      FROM (
        SELECT j.judge,
               COUNT(*) AS decided,
               SUM(CASE WHEN (j.verdict = 'yes' AND c.human_status IN ('pursue', 'submitted'))
                          OR (j.verdict = 'no' AND c.human_status IN ('not_relevant', 'dismissed')) THEN 1 ELSE 0 END) AS matches,
               SUM(CASE WHEN j.verdict = 'no' AND c.human_status IN ('pursue', 'submitted') THEN 1 ELSE 0 END) AS misses,
               SUM(CASE WHEN j.verdict = 'yes' AND c.human_status IN ('not_relevant', 'dismissed') THEN 1 ELSE 0 END) AS false_alarms
        FROM calls AS c
        JOIN judgments AS j ON j.call_id = c.id
        WHERE c.human_status IS NOT NULL
          AND j.id = (SELECT MAX(e.id) FROM judgments AS e
                      WHERE e.call_id = c.id AND e.judge = j.judge
                        AND e.rated_at < COALESCE((SELECT MIN(d.decided_at) FROM decisions AS d WHERE d.call_id = c.id),
                                                  c.human_at))
        GROUP BY j.judge
        ORDER BY j.judge
      ) AS records
      ORDER BY judge`;
    return [...rows];
  } catch {
    return null;   // decisions table missing (migration 004)
  }
}

/**
 * What the judges page scores per person: every decision, the judgments on decided calls, and
 * each decided call with the time it was first decided. Null before migration 004.
 */
export async function scoreboardRows(): Promise<{ decisions: DecisionRow[]; judgments: JudgmentRow[]; calls: DecidedCall[] } | null> {
  try {
    const db = sql();
    const [decisions, judgments, calls] = await Promise.all([
      db<DecisionRow[]>`SELECT call_id, decided_by, status, decided_at FROM decisions ORDER BY id`,
      db<JudgmentRow[]>`
        SELECT j.call_id, j.judge, j.verdict, j.rated_at
        FROM judgments AS j
        WHERE EXISTS (SELECT 1 FROM decisions AS d WHERE d.call_id = j.call_id)
        ORDER BY j.id`,
      db<DecidedCall[]>`
        SELECT c.id, c.title, c.url, c.human_status AS status,
               COALESCE((SELECT MIN(d.decided_at) FROM decisions AS d WHERE d.call_id = c.id), c.human_at) AS decided_at
        FROM calls AS c
        WHERE c.human_status IS NOT NULL
        ORDER BY 5 DESC, c.id`,
    ]);
    return { decisions: [...decisions], judgments: [...judgments], calls: [...calls] };
  } catch {
    return null;   // decisions table missing (migration 004)
  }
}

// ------------------------------------------------------------------------- Monday brief

export type BriefRow = { week_of: string; portal: string | null; body: string; written_by: string; created_at: string };

/** Weeks that have a Monday brief, newest first; null before migration 005. */
export async function briefWeeks(limit = 26): Promise<string[] | null> {
  try {
    const rows = await sql()<{ week_of: string }[]>`
      SELECT DISTINCT week_of FROM briefs ORDER BY week_of DESC LIMIT ${limit}`;
    return rows.map((r) => r.week_of);
  } catch {
    return null;   // briefs table missing (migration 005)
  }
}

/** One week's brief rows, in the order they were written; body is the JSON the Monday job stored. */
export async function briefRows(week: string): Promise<BriefRow[]> {
  const rows = await sql()<BriefRow[]>`
    SELECT week_of, portal, body, written_by, created_at FROM briefs WHERE week_of = ${week} ORDER BY id`;
  return [...rows];
}

export type CallDecision = { status: string | null; by: string | null; at: string | null };

/** The decision each of these calls has now, by call id. */
export async function currentDecisions(ids: string[]): Promise<Map<string, CallDecision>> {
  const found = new Map<string, CallDecision>();
  if (ids.length === 0) return found;
  const db = sql();
  const rows = await db<{ id: string; human_status: string | null; human_by: string | null; human_at: string | null }[]>`
    SELECT id, human_status, human_by, human_at FROM calls WHERE id IN ${db(ids)}`;
  for (const r of rows) found.set(r.id, { status: r.human_status, by: r.human_by, at: r.human_at });
  return found;
}

// -------------------------------------------------------------------- change requests

export type RequestRow = {
  id: number;
  kind: string;
  portal: string | null;
  call_id: string | null;
  summary: string;
  reason: string | null;
  preview: string | null;
  status: string;
  requested_by: string;
  requested_at: string;
  decided_by: string | null;
  decided_at: string | null;
  decision_note: string | null;
  applied_at: string | null;
  result: string | null;
};

const REQUEST_COLUMNS = [
  "id", "kind", "portal", "call_id", "summary", "reason", "preview", "status", "requested_by", "requested_at",
  "decided_by", "decided_at", "decision_note", "applied_at", "result",
];

/** Requests waiting for a person to approve or reject them, oldest first. */
export async function waitingRequests(): Promise<RequestRow[]> {
  const db = sql();
  const rows = await db<RequestRow[]>`
    SELECT ${db(REQUEST_COLUMNS)} FROM change_requests WHERE status = 'proposed' ORDER BY id`;
  return [...rows];
}

/** Requests already decided, newest first. */
export async function decidedRequests(limit = 50): Promise<RequestRow[]> {
  const db = sql();
  const rows = await db<RequestRow[]>`
    SELECT ${db(REQUEST_COLUMNS)} FROM change_requests WHERE status <> 'proposed' ORDER BY id DESC LIMIT ${limit}`;
  return [...rows];
}

/** How many requests wait for a decision; null when the table is not there yet (migration 002 not applied). */
export async function countWaitingRequests(): Promise<number | null> {
  try {
    const [row] = await sql()<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM change_requests WHERE status = 'proposed'`;
    return row?.n ?? 0;
  } catch {
    return null;
  }
}

export type DecideRequestResult = { ok: true; summary: string } | { ok: false; reason: string };

/**
 * Approve or reject a proposed request, the equivalent of decide_request() in Python.
 * Guarded on status = 'proposed', so a request is decided once; the scan machine carries
 * out approved requests (run.py --apply-requests).
 */
export async function decideRequest(input: {
  id: number;
  choice: RequestChoice;
  by: string;
  note: string;
}): Promise<DecideRequestResult> {
  const db = sql();
  const now = isoNow();
  const status = input.choice === "approve" ? "approved" : "rejected";
  const updated = await db<{ summary: string }[]>`
    UPDATE change_requests
    SET status = ${status}, decided_by = ${input.by}, decided_at = ${now},
        decision_note = ${input.note.trim() || null}, updated_at = ${now}
    WHERE id = ${input.id} AND status = 'proposed'
    RETURNING summary`;
  if (updated.length === 1) return { ok: true, summary: updated[0].summary };
  const [existing] = await db<{ status: string; decided_by: string | null }[]>`
    SELECT status, decided_by FROM change_requests WHERE id = ${input.id}`;
  if (!existing) return { ok: false, reason: `There is no request #${input.id}.` };
  return {
    ok: false,
    reason: `Request #${input.id} was already ${existing.status}${existing.decided_by ? ` by ${existing.decided_by}` : ""}. Nothing saved.`,
  };
}

// ------------------------------------------------------------------------------- runs

export type RunRow = {
  id: number;
  component: string;
  portal: string | null;
  started_at: string;
  finished_at: string | null;
  status: string;
  stage_counts: string | null;
  error: string | null;
  log_path: string | null;
  dry_run: number;
};

/** The newest real scan that completed, for the Scans card and Home's status line. */
export async function lastCompletedRun(): Promise<RunRow | null> {
  const [row] = await sql()<RunRow[]>`
    SELECT id, component, portal, started_at, finished_at, status, stage_counts, error, log_path, dry_run
    FROM runs WHERE status = 'completed' AND dry_run = 0 ORDER BY id DESC LIMIT 1`;
  return row ?? null;
}

/** How many real scans have run (dry runs left out), for the Scans card. */
export async function countRuns(): Promise<number> {
  const [row] = await sql()<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM runs WHERE dry_run = 0`;
  return row?.n ?? 0;
}

export async function listRuns(limit = 100): Promise<RunRow[]> {
  const rows = await sql()<RunRow[]>`
    SELECT id, component, portal, started_at, finished_at, status, stage_counts, error, log_path, dry_run
    FROM runs
    ORDER BY id DESC
    LIMIT ${limit}`;
  return [...rows];
}

export async function runLogPath(id: number): Promise<string | null> {
  const [row] = await sql()<{ log_path: string | null }[]>`SELECT log_path FROM runs WHERE id = ${id}`;
  return row?.log_path ?? null;
}

// -------------------------------------------------------------------------- proposals

export type ProposalRow = {
  submission_id: string;
  title: string | null;
  portal: string | null;
  agency: string | null;
  type: string | null;
  submitted_date: string | null;
  outcome: string | null;
  strength_rating: number | null;
  use_as_exemplar: number;
  drive_link: string | null;
};

export async function listProposals(): Promise<ProposalRow[]> {
  const rows = await sql()<ProposalRow[]>`
    SELECT submission_id, title, portal, agency, type, submitted_date, outcome, strength_rating,
           use_as_exemplar, drive_link
    FROM proposals
    ORDER BY submitted_date DESC NULLS LAST, submission_id`;
  return [...rows];
}

export type WinRate = { portal: string | null; won: number; decided: number; win_rate_pct: number | null };

/** "Win rate by portal" from LEDGER_SCHEMA.md, unchanged, wrapped only to cast its numbers. */
export async function winRateByPortal(): Promise<WinRate[]> {
  const rows = await sql()<WinRate[]>`
    SELECT portal, won::int AS won, decided::int AS decided, win_rate_pct::float8 AS win_rate_pct
    FROM (
      SELECT portal,
             SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END) AS won,
             SUM(CASE WHEN outcome IN ('won', 'lost') THEN 1 ELSE 0 END) AS decided,
             ROUND(100.0 * SUM(CASE WHEN outcome = 'won' THEN 1 ELSE 0 END)
                   / NULLIF(SUM(CASE WHEN outcome IN ('won', 'lost') THEN 1 ELSE 0 END), 0), 1) AS win_rate_pct
      FROM proposals
      GROUP BY portal
    ) AS rates
    ORDER BY decided DESC, portal`;
  return [...rows];
}
