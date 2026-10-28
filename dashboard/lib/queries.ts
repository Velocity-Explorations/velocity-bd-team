// Every query the dashboard runs. The SQL follows docs/LEDGER_SCHEMA.md; counts are cast to
// int and rates to float8 because Postgres returns bigint and numeric, which arrive as strings.

import type { TransactionSql } from "postgres";
import { sql } from "./db";
import { CLOSED_PATTERN, portalOptions, type CallState, type PortalOption, type Sort } from "./filters";
import type { JudgeFilter, Judgment } from "./judges";
import type { TagOption, TagRow } from "./tags";
import { isoNow } from "./format";
import type { RequestChoice } from "./requests";
import type { DecidedCall, DecisionRow, JudgmentRow } from "./scoreboard";
import { escapeLike, noteLine } from "./text";
import { isDecision, planDecision, type Decision } from "./values";
import { parseTop } from "./brief";
import type { ProfileFields } from "./profile";
import { startRefusal, workerReadiness, type ProposalCall } from "./proposals";
import { DESCRIPTION_READ } from "./description";
import { STALE_MS } from "./runs";
import { DUE_SOON_DAYS, NEW_DAYS, type CallView } from "./views";
import { NO_GO_STEPS, stateWord, stepInfo, STEPS, type StepRow } from "./workspace";

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
  days_left: number | null;
  description: string | null;
  match_tier: string | null;
  first_seen_at: string;
  extra: string | null;
  human_status: string | null;
  human_notes: string | null;
};

/** The filter panel's choices (lib/filters.ts). No portals ticked means every portal; no tag, any tag. */
export type PanelFilters = { portals: string[]; state: CallState; sort: Sort; judges: JudgeFilter; tag: string };

type Db = ReturnType<typeof sql>;
/** A transaction from db.begin, for the helpers that write inside one. */
type Tx = TransactionSql<Record<string, never>>;

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

/** The header menus' keyword searches (PRO-572): words in the title, the description or Claude's reason. */
export type Keywords = { q?: string; desc?: string; why?: string };

function keywordWhere(db: Db, f: Keywords) {
  return db`
    ${f.q ? db`AND title ILIKE ${`%${escapeLike(f.q)}%`}` : db``}
    ${f.desc ? db`AND description ILIKE ${`%${escapeLike(f.desc)}%`}` : db``}
    ${f.why ? db`AND ai_reasoning ILIKE ${`%${escapeLike(f.why)}%`}` : db``}`;
}

/**
 * The triage backlog, newest first unless sorted otherwise. With `waitingFor` (the names one
 * person's decisions are recorded under, while everyone decides every call): the calls that
 * person has not decided. Otherwise, and before migration 004: the calls nobody has decided,
 * the "Triage backlog" query in LEDGER_SCHEMA.md. A call a later keyword change dropped leaves it.
 * Views narrow it (PRO-571): Due soon to those closing within DUE_SOON_DAYS, New this week to those
 * first seen in the last NEW_DAYS; the judges views through `judges`. Top 10 lists `ids`, decided or
 * not, in the database's order: the page puts them in the brief's.
 */
export async function reviewQueue(
  f: PanelFilters & Keywords & { verdict: string; tier: string; view?: CallView; ids?: string[] },
  waitingFor: string[] | null,
): Promise<{ rows: QueueRow[]; perPerson: boolean }> {
  const db = sql();
  const perPerson = Boolean(waitingFor?.length) && (await hasTable(db, "decisions"));
  if (f.view === "top10" && !f.ids?.length) return { rows: [], perPerson };
  const rows = await db<QueueRow[]>`
    SELECT id, portal, title, url, type, department, naics_code, set_aside, ai_verdict, ai_reasoning, due_date,
           (${dueDate(db)} - CURRENT_DATE)::int AS days_left, left(description, ${DESCRIPTION_READ}::int) AS description,
           match_tier, first_seen_at, extra, human_status, human_notes
    FROM calls
    WHERE ${f.view === "top10" ? db`id IN ${db(f.ids ?? [])}` : waitingWhere(db, perPerson, waitingFor)}
      ${f.view === "due-soon" ? db`AND ${dueSoon(db)}` : db``}
      ${f.view === "new" ? db`AND first_seen_at >= ${newSince()}` : db``}
      ${f.verdict ? db`AND ai_verdict = ${f.verdict}` : db``}
      ${f.tier ? db`AND match_tier = ${f.tier}` : db``}
      ${keywordWhere(db, f)}
      ${panelWhere(db, f)}
    ${panelOrder(db, f)}
    LIMIT 500`;
  return { rows: [...rows], perPerson };
}

/** The first-seen time from which a call is New this week. */
function newSince(now: Date = new Date()): string {
  return isoNow(new Date(now.getTime() - NEW_DAYS * 24 * 3600 * 1000));
}

export type QueueCounts = { waiting: number; dueSoon: number; yes: number; agree: number; disagree: number; fresh: number };

/**
 * The waiting calls' view counts under the bar's filters (VC2); the column filters do not narrow them:
 * all of them, Due soon, yes, Judges agree, Judges disagree and New this week.
 */
export async function queueCounts(f: BarFilters, waitingFor: string[] | null): Promise<QueueCounts> {
  const db = sql();
  const perPerson = Boolean(waitingFor?.length) && (await hasTable(db, "decisions"));
  const [row] = await db<{ waiting: number; due_soon: number; yes: number; agree: number; disagree: number; fresh: number }[]>`
    SELECT COUNT(*)::int AS waiting,
           COUNT(*) FILTER (WHERE ${dueSoon(db)})::int AS due_soon,
           COUNT(*) FILTER (WHERE ai_verdict = 'yes')::int AS yes,
           COUNT(*) FILTER (WHERE ${newestVerdict(db, "claude")} = ${newestVerdict(db, "grok")})::int AS agree,
           COUNT(*) FILTER (WHERE ${newestVerdict(db, "claude")} <> ${newestVerdict(db, "grok")})::int AS disagree,
           COUNT(*) FILTER (WHERE first_seen_at >= ${newSince()})::int AS fresh
    FROM calls
    WHERE ${waitingWhere(db, perPerson, waitingFor)}
      ${panelWhere(db, barOnly(f))}`;
  return {
    waiting: row?.waiting ?? 0, dueSoon: row?.due_soon ?? 0, yes: row?.yes ?? 0,
    agree: row?.agree ?? 0, disagree: row?.disagree ?? 0, fresh: row?.fresh ?? 0,
  };
}

/** How many of these calls (the Top 10) the bar's filters leave, for its card. */
export async function countAmong(ids: string[], f: BarFilters): Promise<number> {
  if (ids.length === 0) return 0;
  const db = sql();
  const [row] = await db<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM calls WHERE id IN ${db(ids)} ${panelWhere(db, barOnly(f))}`;
  return row?.n ?? 0;
}

/** All calls' count under the bar's filters, for its card. */
export async function countCalls(f: BarFilters): Promise<number> {
  const db = sql();
  const [row] = await db<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM calls WHERE TRUE ${panelWhere(db, barOnly(f))}`;
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

/** This week's Top 10: the newest Monday brief's, in its order, or the live ranking before the first brief (H2). */
export async function topTenIds(): Promise<{ ids: string[]; week: string | null }> {
  const weeks = await briefWeeks();
  if (weeks && weeks.length) {
    const rows = await briefRows(weeks[0]);
    const top = parseTop(rows.find((r) => r.portal === null)?.body);
    if (top) return { ids: top.top.map((c) => c.id), week: weeks[0] };
  }
  return { ids: await liveTopTen(), week: null };
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

export type CallFilters = PanelFilters & Keywords & { filterResult: string; verdict: string; status: string };

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
  days_left: number | null;
  description: string | null;
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
      ${keywordWhere(db, f)}
      ${panelWhere(db, f)}`;
  const [count, rows] = await Promise.all([
    db<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM calls ${where()}`,
    db<CallRow[]>`
      SELECT id, portal, title, url, type, department, naics_code, set_aside, due_date,
             (${dueDate(db)} - CURRENT_DATE)::int AS days_left, left(description, ${DESCRIPTION_READ}::int) AS description,
             filter_result, filter_reason, match_tier,
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
  const drafts = input.status === "submitted" && (await hasTable(db, "pursuits"));
  const mine = history ? await latestDecisionBy(db, input.id, input.aliases) : null;
  const now = isoNow();
  const line = noteLine(now, input.by, input.note) || null;
  return db.begin(async (tx): Promise<DecideResult> => {
    const [call] = await tx<{ title: string | null; human_status: string | null; human_by: string | null }[]>`
      SELECT title, human_status, human_by FROM calls WHERE id = ${input.id} FOR UPDATE`;
    if (!call) return { ok: false, reason: "That call is no longer in the ledger." };
    if (drafts) {
      // A call whose draft is under way is marked submitted at its Submit gate, which records the confirmation (P7).
      const [working] = await tx`SELECT 1 FROM pursuits WHERE call_id = ${input.id} AND state = 'working'`;
      if (working) return { ok: false, reason: "This call has a draft under way: mark it submitted at the Submit gate in its workspace." };
    }
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

/** How many requests have been decided, for the Decided requests card. */
export async function countDecidedRequests(): Promise<number> {
  try {
    const [row] = await sql()<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM change_requests WHERE status <> 'proposed'`;
    return row?.n ?? 0;
  } catch {
    return 0;
  }
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

/** Scans' filters (PRO-573): portals (none means every one), Scan problems only, and the Started sort. */
export type RunFilters = { portals?: string[]; problems?: boolean; dir?: "asc" | "desc" };

/** Runs that failed, timed out, or still say running two hours after they started (lib/runs.ts). */
function problemWhere(db: Db) {
  const staleBefore = isoNow(new Date(Date.now() - STALE_MS));
  return db`(status IN ('error', 'skipped_timeout') OR (status = 'running' AND finished_at IS NULL AND started_at < ${staleBefore}))`;
}

export async function listRuns(limit = 100, f: RunFilters = {}): Promise<RunRow[]> {
  const db = sql();
  const rows = await db<RunRow[]>`
    SELECT id, component, portal, started_at, finished_at, status, stage_counts, error, log_path, dry_run
    FROM runs
    WHERE TRUE
      ${f.portals?.length ? db`AND portal IN ${db(f.portals)}` : db``}
      ${f.problems ? db`AND ${problemWhere(db)}` : db``}
    ORDER BY started_at ${f.dir === "asc" ? db`ASC` : db`DESC`}, id ${f.dir === "asc" ? db`ASC` : db`DESC`}
    LIMIT ${limit}`;
  return [...rows];
}

/** How many real scans failed, timed out or never finished, for the Scan problems card. */
export async function countProblemRuns(): Promise<number> {
  const db = sql();
  const [row] = await db<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM runs WHERE dry_run = 0 AND ${problemWhere(db)}`;
  return row?.n ?? 0;
}

/** The portals that have runs, for Scans' Portals filter. */
export async function runPortals(): Promise<string[]> {
  const rows = await sql()<{ portal: string }[]>`SELECT DISTINCT portal FROM runs WHERE portal IS NOT NULL ORDER BY portal`;
  return rows.map((r) => r.portal);
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

/** The Proposal Register's submissions, newest first, optionally from some portals only. */
export async function listProposals(portals: string[] = [], dir: "asc" | "desc" = "desc"): Promise<ProposalRow[]> {
  const db = sql();
  const rows = await db<ProposalRow[]>`
    SELECT submission_id, title, portal, agency, type, submitted_date, outcome, strength_rating,
           use_as_exemplar, drive_link
    FROM proposals
    ${portals.length ? db`WHERE portal IN ${db(portals)}` : db``}
    ORDER BY submitted_date ${dir === "asc" ? db`ASC` : db`DESC`} NULLS LAST, submission_id`;
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

// ------------------------------------------------------------------------------ pursuits

/**
 * Every pursued, drafting or submitted call under the bar's filters, with its pursuit if it has one
 * and the state of the pursuit's current step (PRO-575). lib/proposals.ts sorts them into the views.
 * The result is expected 90 days after the deadline unless Discovery found a date.
 */
export async function proposalCalls(f: BarFilters): Promise<ProposalCall[]> {
  const db = sql();
  if (!(await hasTable(db, "pursuits"))) {
    const rows = await db<ProposalCall[]>`
      SELECT calls.id, portal, title, url, type, department, naics_code, set_aside, due_date,
             (${dueDate(db)} - CURRENT_DATE)::int AS days_left, to_char(${dueDate(db)} + 90, 'YYYY-MM-DD') AS default_result_by,
             extra, ai_verdict, ai_reasoning, human_status, human_by, human_at,
             NULL::int AS pursuit_id, NULL AS owner, NULL AS pursuit_state, NULL AS current_step, NULL AS step_state,
             NULL AS drive_folder_id, NULL AS submitted_at, NULL AS submitted_by, NULL AS confirmation_number,
             NULL AS result_expected_by, NULL AS result_expected_source, NULL AS result, NULL AS result_at
      FROM calls
      WHERE human_status IN ('pursue', 'submitted') ${panelWhere(db, barOnly(f))}`;
    return [...rows];
  }
  const rows = await db<ProposalCall[]>`
    SELECT calls.id, calls.portal, calls.title, calls.url, calls.type, calls.department, calls.naics_code, calls.set_aside,
           calls.due_date, (${dueDate(db)} - CURRENT_DATE)::int AS days_left,
           to_char(${dueDate(db)} + 90, 'YYYY-MM-DD') AS default_result_by,
           calls.extra, calls.ai_verdict, calls.ai_reasoning, calls.human_status, calls.human_by, calls.human_at,
           p.id AS pursuit_id, p.owner, p.state AS pursuit_state, p.current_step, s.state AS step_state, p.drive_folder_id,
           p.submitted_at, p.submitted_by, p.confirmation_number, p.result_expected_by, p.result_expected_source,
           p.result, p.result_at
    FROM calls
    LEFT JOIN pursuits AS p ON p.call_id = calls.id
    LEFT JOIN pursuit_steps AS s
      ON s.id = (SELECT MAX(x.id) FROM pursuit_steps AS x WHERE x.pursuit_id = p.id AND x.step = p.current_step)
    WHERE (calls.human_status IN ('pursue', 'submitted') OR p.id IS NOT NULL)
      ${panelWhere(db, barOnly(f))}`;
  return [...rows];
}

/** The worker's newest heartbeat (PRO-576), or null when it has never run or migration 008 is missing. */
export async function workerStatus(): Promise<{ name: string; seen_at: string; state: string } | null> {
  const db = sql();
  if (!(await hasTable(db, "workers"))) return null;
  const [row] = await db<{ name: string; seen_at: string; state: string }[]>`
    SELECT name, seen_at, state FROM workers ORDER BY seen_at DESC LIMIT 1`;
  return row ?? null;
}

/** A call's draft as its badge and the Decide cell show it (DB1 to DB3, Q17). */
export type DraftInfo = {
  call_id: string;
  owner: string;
  pursuit_state: string;
  current_step: string | null;
  step_state: string | null;
  drive_folder_id: string | null;
  submitted_at: string | null;
  submitted_by: string | null;
  result_expected_by: string | null;
};

/** The drafts of these calls, by call id; empty before migration 008. */
export async function draftsFor(callIds: string[]): Promise<Map<string, DraftInfo>> {
  const found = new Map<string, DraftInfo>();
  if (callIds.length === 0) return found;
  const db = sql();
  if (!(await hasTable(db, "pursuits"))) return found;
  const rows = await db<DraftInfo[]>`
    SELECT p.call_id, p.owner, p.state AS pursuit_state, p.current_step, s.state AS step_state, p.drive_folder_id,
           p.submitted_at, p.submitted_by, p.result_expected_by
    FROM pursuits AS p
    LEFT JOIN pursuit_steps AS s
      ON s.id = (SELECT MAX(x.id) FROM pursuit_steps AS x WHERE x.pursuit_id = p.id AND x.step = p.current_step)
    WHERE p.call_id IN ${db(callIds)}`;
  for (const row of rows) found.set(row.call_id, row);
  return found;
}

export type StartResult = { ok: true; title: string } | { ok: false; reason: string };

/**
 * Start the draft (P6, PRO-576): the pursuit, its Discovery step queued for the worker, and the first
 * line of its history, in one transaction, as ledger/queries.py's start_pursuit writes them. Refused
 * with the reason (startRefusal) for a second draft, a call marked Not relevant or not pursued, a
 * closed call, one whose solicitation the worker cannot read, or before the worker has ever run.
 */
export async function startPursuit(input: {
  callId: string;
  owner: string;
  format: string;
  approvalMode: "every_step" | "key_gates";
  direction: string;
  collaborators: string[];
}): Promise<StartResult> {
  const db = sql();
  if (!(await hasTable(db, "pursuits"))) return { ok: false, reason: "Drafting needs ledger migration 008." };
  const readiness = workerReadiness(await workerStatus(), new Date());
  const now = isoNow();
  const mode = input.approvalMode === "key_gates" ? "key gates only" : "every step approved";
  return db.begin(async (tx): Promise<StartResult> => {
    const [call] = await tx<{ human_status: string | null; extra: string | null; title: string | null }[]>`
      SELECT human_status, extra, title FROM calls WHERE id = ${input.callId} FOR UPDATE`;
    if (!call) return { ok: false, reason: "That call is no longer in the ledger." };
    const [held] = await tx<{ owner: string; created_at: string }[]>`SELECT owner, created_at FROM pursuits WHERE call_id = ${input.callId}`;
    const refusal = startRefusal(call, held ?? null, readiness);
    if (refusal) return { ok: false, reason: refusal };
    const [pursuit] = await tx<{ id: number }[]>`
      INSERT INTO pursuits (call_id, owner, collaborators, format, approval_mode, direction, current_step, state, created_at, updated_at)
      VALUES (${input.callId}, ${input.owner}, ${input.collaborators.length ? JSON.stringify(input.collaborators) : null},
              ${input.format}, ${input.approvalMode}, ${input.direction.trim() || null}, 'discovery', 'working', ${now}, ${now})
      RETURNING id`;
    const [step] = await tx<{ id: number }[]>`
      INSERT INTO pursuit_steps (pursuit_id, step, attempt, state, requested_by, queued_at, updated_at)
      VALUES (${pursuit.id}, 'discovery', 1, 'queued', ${input.owner}, ${now}, ${now})
      RETURNING id`;
    await tx`
      INSERT INTO pursuit_events (pursuit_id, step_id, at, who, kind, text)
      VALUES (${pursuit.id}, ${step.id}, ${now}, ${input.owner}, 'started', ${`Started the draft: ${input.format}, ${mode}`})`;
    return { ok: true, title: call.title ?? input.callId };
  });
}

// ------------------------------------------------------------------------------- profiles

export type ProfileRow = {
  name: string;
  display_name: string | null;
  initials: string | null;
  opens: string;
  default_filters: string | null;
  time_zone: string | null;
  updated_at: string;
};

/** Every saved profile, by name (PRO-574); empty before migration 008. */
export async function allProfiles(): Promise<Map<string, ProfileRow>> {
  const db = sql();
  if (!(await hasTable(db, "profiles"))) return new Map();
  const rows = await db<ProfileRow[]>`
    SELECT name, display_name, initials, opens, default_filters, time_zone, updated_at FROM profiles`;
  return new Map(rows.map((r) => [r.name, r]));
}

/** Profile settings' Save: one row per person, replaced whole. */
export async function saveProfile(name: string, f: ProfileFields): Promise<void> {
  const now = isoNow();
  await sql()`
    INSERT INTO profiles (name, display_name, initials, opens, default_filters, time_zone, updated_at)
    VALUES (${name}, ${f.display_name}, ${f.initials}, ${f.opens},
            ${f.default_filters ? JSON.stringify(f.default_filters) : null}, ${f.time_zone}, ${now})
    ON CONFLICT (name) DO UPDATE SET
      display_name = EXCLUDED.display_name, initials = EXCLUDED.initials, opens = EXCLUDED.opens,
      default_filters = EXCLUDED.default_filters, time_zone = EXCLUDED.time_zone, updated_at = EXCLUDED.updated_at`;
}

/** Profile settings' Reset to defaults: the person's row goes, so every default applies. */
export async function deleteProfile(name: string): Promise<void> {
  await sql()`DELETE FROM profiles WHERE name = ${name}`;
}

// ----------------------------------------------------------------- the proposal workspace

/** A pursuit as the workspace shows it (pursuits, migration 008). */
export type PursuitRow = {
  id: number;
  call_id: string;
  owner: string;
  collaborators: string | null;
  format: string | null;
  approval_mode: string;
  direction: string | null;
  builds_on: string | null;
  drive_folder_id: string | null;
  drive_folder_name: string | null;
  current_step: string;
  state: string;
  target_dates: string | null;
  cost_usd: number;
  budget_usd: number;
  submitted_at: string | null;
  submitted_by: string | null;
  result_expected_by: string | null;
  created_at: string;
  updated_at: string;
};

export type EventRow = { id: number; step_id: number | null; at: string; who: string; kind: string; text: string };

export type ChecklistRow = {
  id: number;
  part: string;
  position: number;
  text: string;
  source: string | null;
  owner: string | null;
  due_date: string | null;
  origin: string;
  done: number;
  done_by: string | null;
  done_at: string | null;
};

export type WorkspaceCall = {
  id: string;
  portal: string;
  title: string | null;
  url: string | null;
  type: string | null;
  due_date: string | null;
  days_left: number | null;
  human_status: string | null;
};

export type Workspace = { call: WorkspaceCall; pursuit: PursuitRow | null; steps: StepRow[]; events: EventRow[]; checklist: ChecklistRow[] };

/** A call, its pursuit, every attempt at every step, the history newest first, and the checklist (PW1). */
export async function workspace(callId: string): Promise<Workspace | null> {
  const db = sql();
  const [call] = await db<WorkspaceCall[]>`
    SELECT id, portal, title, url, type, due_date, (${dueDate(db)} - CURRENT_DATE)::int AS days_left, human_status
    FROM calls WHERE id = ${callId}`;
  if (!call) return null;
  const empty: Workspace = { call, pursuit: null, steps: [], events: [], checklist: [] };
  if (!(await hasTable(db, "pursuits"))) return empty;
  const [pursuit] = await db<PursuitRow[]>`SELECT * FROM pursuits WHERE call_id = ${callId}`;
  if (!pursuit) return empty;
  const [steps, events, checklist] = await Promise.all([
    db<StepRow[]>`SELECT * FROM pursuit_steps WHERE pursuit_id = ${pursuit.id} ORDER BY id`,
    db<EventRow[]>`SELECT id, step_id, at, who, kind, text FROM pursuit_events WHERE pursuit_id = ${pursuit.id} ORDER BY id DESC`,
    db<ChecklistRow[]>`SELECT * FROM checklist_items WHERE pursuit_id = ${pursuit.id} ORDER BY position, id`,
  ]);
  return { call, pursuit, steps: [...steps], events: [...events], checklist: [...checklist] };
}

export type WorkspaceResult = { ok: true; notice: string } | { ok: false; reason: string };

/** A step's name in history: its label, with the attempt after the first (as ledger/queries.py writes it). */
function stepName(r: { step: string; attempt: number }): string {
  const label = stepInfo(r.step)?.label ?? r.step;
  return r.attempt > 1 ? `${label} (attempt ${r.attempt})` : label;
}

function staleReason(r: StepRow): string {
  return `This step changed since the page loaded: it is ${stateWord(r)} now. Nothing saved; reload to see it.`;
}

/** The next attempt at a step, queued for the worker, and the pursuit's current step (ledger/queries.py `_queue_step`). */
async function queueStep(tx: Tx, pursuitId: number, step: string, by: string, note: string | null, now: string): Promise<number> {
  const [last] = await tx<{ n: number | null }[]>`
    SELECT MAX(attempt) AS n FROM pursuit_steps WHERE pursuit_id = ${pursuitId} AND step = ${step}`;
  const [row] = await tx<{ id: number }[]>`
    INSERT INTO pursuit_steps (pursuit_id, step, attempt, state, requested_by, request_note, queued_at, updated_at)
    VALUES (${pursuitId}, ${step}, ${Number(last?.n ?? 0) + 1}, 'queued', ${by}, ${note}, ${now}, ${now})
    RETURNING id`;
  await tx`UPDATE pursuits SET current_step = ${step}, updated_at = ${now} WHERE id = ${pursuitId}`;
  return row.id;
}

async function addEvent(tx: Tx, pursuitId: number, who: string, kind: string, text: string, stepId: number | null, now: string) {
  await tx`
    INSERT INTO pursuit_events (pursuit_id, step_id, at, who, kind, text)
    VALUES (${pursuitId}, ${stepId}, ${now}, ${who}, ${kind}, ${text})`;
}

function withNote(text: string, note: string): string {
  return note.trim() ? `${text}: ${note.trim()}` : text;
}

/**
 * Approve and continue (PW4), or Go and Go with conditions at the gate (PW10): ready -> approved, and the
 * next step queued for the worker. Each condition joins the checklist as an item the owner owns. Guarded by
 * the step's state and the updated_at the page showed, and the pursuit still being worked.
 */
export async function approveStep(input: {
  stepId: number;
  by: string;
  expected: string;
  decision?: string;
  note?: string;
  conditions?: string[];
}): Promise<WorkspaceResult> {
  const db = sql();
  return db.begin(async (tx): Promise<WorkspaceResult> => {
    const [r] = await tx<StepRow[]>`SELECT * FROM pursuit_steps WHERE id = ${input.stepId} FOR UPDATE`;
    if (!r) return { ok: false, reason: "That step is no longer in the ledger." };
    const at = STEPS.findIndex((s) => s.name === r.step);
    const following = STEPS[at + 1]?.name;
    if (!following || r.step === "submit") return { ok: false, reason: "Submit is recorded with Mark submitted." };
    const chosen = r.step === "go_no_go" ? (input.decision === "go_with_conditions" ? "go_with_conditions" : "go") : "approved";
    const conditions = (input.conditions ?? []).map((c) => c.trim()).filter(Boolean);
    if (chosen === "go_with_conditions" && conditions.length === 0) {
      return { ok: false, reason: "Go with conditions needs at least one condition, one per line." };
    }
    const now = isoNow();
    const note = (input.note ?? "").trim();
    const done = await tx`
      UPDATE pursuit_steps SET state = 'approved', decision = ${chosen}, decided_by = ${input.by}, decided_at = ${now},
             decision_note = ${note || (conditions.length ? conditions.join("\n") : null)}, updated_at = ${now}
      WHERE id = ${input.stepId} AND state = 'ready' AND updated_at = ${input.expected}
        AND pursuit_id IN (SELECT id FROM pursuits WHERE state = 'working')
      RETURNING id`;
    if (done.length !== 1) return { ok: false, reason: staleReason(r) };
    await queueStep(tx, r.pursuit_id, following, input.by, null, now);
    if (chosen === "go_with_conditions") {
      const [last] = await tx<{ n: number | null }[]>`SELECT MAX(position) AS n FROM checklist_items WHERE pursuit_id = ${r.pursuit_id}`;
      let position = Number(last?.n ?? -1) + 1;
      for (const condition of conditions) {
        await tx`
          INSERT INTO checklist_items (pursuit_id, part, position, text, source, owner, due_date, origin, done, created_at, updated_at)
          VALUES (${r.pursuit_id}, 'inputs', ${position++}, ${condition}, 'Go with conditions', ${input.by}, NULL, 'condition', 0, ${now}, ${now})`;
      }
    }
    const text = chosen === "approved" ? withNote(`${stepName(r)} approved`, note)
      : chosen === "go" ? withNote("Go", note) : `Go with conditions: ${conditions.join("; ")}`;
    await addEvent(tx, r.pursuit_id, input.by, chosen, text, r.id, now);
    const next = stepInfo(following)?.label ?? following;
    return { ok: true, notice: chosen === "approved" ? `Approved. ${next} is queued for the worker.`
      : `${chosen === "go" ? "Go" : "Go with conditions"} recorded. ${next} is queued for the worker.` };
  });
}

/** Ask for changes (PW4): ready -> changes_asked, and the step queued again with the note for the worker. */
export async function askChanges(input: { stepId: number; by: string; expected: string; note: string }): Promise<WorkspaceResult> {
  const note = input.note.trim();
  if (!note) return { ok: false, reason: "Say what to change: the note goes to Claude with the step." };
  const db = sql();
  return db.begin(async (tx): Promise<WorkspaceResult> => {
    const [r] = await tx<StepRow[]>`SELECT * FROM pursuit_steps WHERE id = ${input.stepId} FOR UPDATE`;
    if (!r) return { ok: false, reason: "That step is no longer in the ledger." };
    const now = isoNow();
    const done = await tx`
      UPDATE pursuit_steps SET state = 'changes_asked', decision = 'changes_asked', decided_by = ${input.by}, decided_at = ${now},
             decision_note = ${note}, updated_at = ${now}
      WHERE id = ${input.stepId} AND state = 'ready' AND updated_at = ${input.expected}
        AND pursuit_id IN (SELECT id FROM pursuits WHERE state = 'working')
      RETURNING id`;
    if (done.length !== 1) return { ok: false, reason: staleReason(r) };
    await queueStep(tx, r.pursuit_id, r.step, input.by, note, now);
    await addEvent(tx, r.pursuit_id, input.by, "changes_asked", `Asked for changes to ${stepName(r)}: ${note}`, r.id, now);
    return { ok: true, notice: `Asked for changes. ${stepInfo(r.step)?.label ?? r.step} is queued again for the worker.` };
  });
}

async function retryIn(tx: Tx, r: StepRow, by: string, now: string): Promise<boolean> {
  const done = await tx`
    UPDATE pursuit_steps SET decision = 'retried', decided_by = ${by}, decided_at = ${now}, updated_at = ${now}
    WHERE id = ${r.id} AND state IN ('failed', 'blocked') AND decision IS NULL
      AND pursuit_id IN (SELECT id FROM pursuits WHERE state = 'working')
    RETURNING id`;
  if (done.length !== 1) return false;
  const redo = await queueStep(tx, r.pursuit_id, r.step, by, null, now);
  await addEvent(tx, r.pursuit_id, by, "retried", `Retried ${stepInfo(r.step)?.label ?? r.step}`, redo, now);
  return true;
}

/** Retry a failed or blocked attempt as a new one (PW15, PW19); the old attempt keeps its error. */
export async function retryStep(input: { stepId: number; by: string }): Promise<WorkspaceResult> {
  const db = sql();
  return db.begin(async (tx): Promise<WorkspaceResult> => {
    const [r] = await tx<StepRow[]>`SELECT * FROM pursuit_steps WHERE id = ${input.stepId} FOR UPDATE`;
    if (!r) return { ok: false, reason: "That step is no longer in the ledger." };
    if (!(await retryIn(tx, r, input.by, isoNow()))) return { ok: false, reason: staleReason(r) };
    return { ok: true, notice: `${stepInfo(r.step)?.label ?? r.step} is queued again for the worker.` };
  });
}

/**
 * Stop here, no-go (PW4, steps 1 to 4) or No-go at the gate (PW10): the step stops with the reason and the
 * pursuit becomes no_go. The caller then records the call as Not relevant (P7).
 */
export async function noGoStep(input: { stepId: number; by: string; expected: string; note: string }): Promise<WorkspaceResult> {
  const note = input.note.trim();
  if (!note) return { ok: false, reason: "No-go needs the reason, and what would change the answer." };
  const db = sql();
  return db.begin(async (tx): Promise<WorkspaceResult> => {
    const [r] = await tx<StepRow[]>`SELECT * FROM pursuit_steps WHERE id = ${input.stepId} FOR UPDATE`;
    if (!r) return { ok: false, reason: "That step is no longer in the ledger." };
    if (![...NO_GO_STEPS, "go_no_go"].includes(r.step)) return { ok: false, reason: "No-go is offered on steps 1 to 4 and the gate." };
    const now = isoNow();
    const done = await tx`
      UPDATE pursuit_steps SET state = 'stopped', decision = 'no_go', decided_by = ${input.by}, decided_at = ${now},
             decision_note = ${note}, updated_at = ${now}
      WHERE id = ${input.stepId} AND state = 'ready' AND updated_at = ${input.expected}
        AND pursuit_id IN (SELECT id FROM pursuits WHERE state = 'working')
      RETURNING id`;
    if (done.length !== 1) return { ok: false, reason: staleReason(r) };
    await tx`UPDATE pursuits SET state = 'no_go', updated_at = ${now} WHERE id = ${r.pursuit_id} AND state = 'working'`;
    await addEvent(tx, r.pursuit_id, input.by, "no_go", `No-go at ${stepName(r)}: ${note}`, r.id, now);
    return { ok: true, notice: "No-go recorded." };
  });
}

/** Raise the cap (PW19): a higher budget, and the step that reached it queued again. */
export async function raiseCap(input: { pursuitId: number; by: string; budget: number }): Promise<WorkspaceResult> {
  const db = sql();
  return db.begin(async (tx): Promise<WorkspaceResult> => {
    const now = isoNow();
    const raised = await tx<{ current_step: string }[]>`
      UPDATE pursuits SET budget_usd = ${input.budget}, updated_at = ${now}
      WHERE id = ${input.pursuitId} AND state = 'working' AND budget_usd < ${input.budget}
      RETURNING current_step`;
    if (raised.length !== 1) return { ok: false, reason: "The cap is already that high, or the draft is no longer being worked." };
    await addEvent(tx, input.pursuitId, input.by, "budget", `Raised the cap to $${input.budget.toFixed(2)}`, null, now);
    const [blocked] = await tx<StepRow[]>`
      SELECT * FROM pursuit_steps WHERE pursuit_id = ${input.pursuitId} AND state = 'blocked' AND decision IS NULL
      ORDER BY id DESC LIMIT 1`;
    const again = blocked ? await retryIn(tx, blocked, input.by, now) : false;
    return { ok: true, notice: `The cap is $${input.budget.toFixed(2)}.${again ? " The step is queued again for the worker." : ""}` };
  });
}

/** Add material (PW4, PW24): a note or a link for Claude, kept in the history; the worker reads it. */
export async function addMaterial(input: { pursuitId: number; who: string; text: string; stepId: number | null }): Promise<WorkspaceResult> {
  const text = input.text.trim();
  if (!text) return { ok: false, reason: "Add the material first: a note, or a link to a page or file." };
  const db = sql();
  return db.begin(async (tx): Promise<WorkspaceResult> => {
    const [pursuit] = await tx<{ state: string }[]>`SELECT state FROM pursuits WHERE id = ${input.pursuitId}`;
    if (pursuit?.state !== "working") return { ok: false, reason: "This draft is no longer being worked." };
    await addEvent(tx, input.pursuitId, input.who, "material", text, input.stepId, isoNow());
    return { ok: true, notice: "Material added. Claude reads it from the next step on." };
  });
}

/** Tick or untick a checklist item (PW9, PW24), guarded on the state the person saw. */
export async function tickChecklist(input: { itemId: number; by: string; done: boolean; expectedDone: boolean }): Promise<WorkspaceResult> {
  const db = sql();
  return db.begin(async (tx): Promise<WorkspaceResult> => {
    const now = isoNow();
    const [item] = await tx<{ pursuit_id: number; text: string }[]>`
      UPDATE checklist_items SET done = ${input.done ? 1 : 0}, done_by = ${input.done ? input.by : null},
             done_at = ${input.done ? now : null}, updated_at = ${now}
      WHERE id = ${input.itemId} AND done = ${input.expectedDone ? 1 : 0}
        AND pursuit_id IN (SELECT id FROM pursuits WHERE state = 'working')
      RETURNING pursuit_id, text`;
    if (!item) return { ok: false, reason: "That item changed since the page loaded. Nothing saved; reload to see it." };
    await addEvent(tx, item.pursuit_id, input.by, "checklist", `${input.done ? "Ticked" : "Unticked"}: ${item.text}`, null, now);
    return { ok: true, notice: `${input.done ? "Ticked" : "Unticked"}: ${item.text}` };
  });
}
