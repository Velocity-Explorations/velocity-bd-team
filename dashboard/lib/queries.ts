// Every query the dashboard runs. The SQL follows docs/LEDGER_SCHEMA.md; counts are cast to
// int and rates to float8 because Postgres returns bigint and numeric, which arrive as strings.

import { sql } from "./db";
import { isoNow } from "./format";
import type { RequestChoice } from "./requests";
import { escapeLike, isClosed, noteLine } from "./text";
import { planDecision, type Decision } from "./values";

// ------------------------------------------------------------------------------ calls

export type QueueRow = {
  id: string;
  portal: string;
  title: string | null;
  url: string | null;
  ai_verdict: string;
  ai_reasoning: string | null;
  due_date: string | null;
  match_tier: string | null;
  first_seen_at: string;
  extra: string | null;
};

/** The triage backlog from LEDGER_SCHEMA.md, newest first. A call a later keyword change dropped leaves it. */
export async function reviewQueue(f: { portal: string; verdict: string; openOnly: boolean }): Promise<QueueRow[]> {
  const db = sql();
  const rows = await db<QueueRow[]>`
    SELECT id, portal, title, url, ai_verdict, ai_reasoning, due_date, match_tier, first_seen_at, extra
    FROM calls
    WHERE ai_verdict IN ('yes', 'maybe')
      AND human_status IS NULL
      AND filter_result = 'kept'
      ${f.portal ? db`AND portal = ${f.portal}` : db``}
      ${f.verdict ? db`AND ai_verdict = ${f.verdict}` : db``}
    ORDER BY first_seen_at DESC, id
    LIMIT 500`;
  return f.openOnly ? rows.filter((r) => !isClosed(r.extra)) : [...rows];
}

/** "New calls this week" from LEDGER_SCHEMA.md, as a count. */
export async function newThisWeek(): Promise<number> {
  const cutoff = isoNow(new Date(Date.now() - 7 * 24 * 3600 * 1000));
  const [row] = await sql()<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM calls WHERE first_seen_at >= ${cutoff}`;
  return row?.n ?? 0;
}

export async function portals(): Promise<string[]> {
  const rows = await sql()<{ portal: string }[]>`SELECT DISTINCT portal FROM calls WHERE portal IS NOT NULL ORDER BY portal`;
  return rows.map((r) => r.portal);
}

export type CallFilters = { portal: string; filterResult: string; verdict: string; status: string; q: string };

export type CallRow = {
  id: string;
  portal: string;
  title: string | null;
  url: string | null;
  type: string | null;
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
      ${f.portal ? db`AND portal = ${f.portal}` : db``}
      ${f.filterResult ? db`AND filter_result = ${f.filterResult}` : db``}
      ${f.verdict === "none" ? db`AND ai_verdict IS NULL` : f.verdict ? db`AND ai_verdict = ${f.verdict}` : db``}
      ${f.status === "none" ? db`AND human_status IS NULL` : f.status ? db`AND human_status = ${f.status}` : db``}
      ${f.q ? db`AND title ILIKE ${`%${escapeLike(f.q)}%`}` : db``}`;
  const [count, rows] = await Promise.all([
    db<{ n: number }[]>`SELECT COUNT(*)::int AS n FROM calls ${where()}`,
    db<CallRow[]>`
      SELECT id, portal, title, url, type, due_date, filter_result, filter_reason, match_tier,
             ai_verdict, ai_reasoning, human_status, human_by, human_at, human_notes, first_seen_at, extra
      FROM calls ${where()}
      ORDER BY first_seen_at DESC, id
      LIMIT ${limit}`,
  ]);
  return { rows: [...rows], total: count[0]?.n ?? 0 };
}

export type DecideResult = { ok: true; title: string; plan: "decide" | "note" } | { ok: false; reason: string };

/**
 * The dashboard's one write, and since 2026-10-17 the only place decisions are made:
 * human_status, human_by, human_at, plus an optional note appended in append_note()'s
 * format. `expected` is the decision the page showed; if the call changed since (another
 * tab, another person), nothing is written and the reason says what it is now.
 */
export async function decideCall(input: {
  id: string;
  status: Decision;
  expected: Decision | null;
  by: string;
  note: string;
}): Promise<DecideResult> {
  const plan = planDecision(input.expected, input.status, input.note);
  if (plan === "noop") return { ok: false, reason: "Nothing to save: choose a different decision or add a note." };
  const db = sql();
  const now = isoNow();
  const line = noteLine(now, input.by, input.note) || null;
  const appendNote = db`human_notes = CASE
      WHEN ${line}::text IS NULL THEN human_notes
      ELSE COALESCE(NULLIF(human_notes, '') || chr(10), '') || ${line}::text
    END`;
  const updated = await db<{ title: string | null }[]>`
    UPDATE calls
    SET ${plan === "decide" ? db`human_status = ${input.status}, human_by = ${input.by}, human_at = ${now},` : db``}
        updated_at = ${now},
        ${appendNote}
    WHERE id = ${input.id}
      AND human_status IS NOT DISTINCT FROM ${input.expected}::text
    RETURNING title`;
  if (updated.length === 1) return { ok: true, title: updated[0].title ?? input.id, plan };
  const [existing] = await db<{ human_status: string | null; human_by: string | null }[]>`
    SELECT human_status, human_by FROM calls WHERE id = ${input.id}`;
  if (!existing) return { ok: false, reason: "That call is no longer in the ledger." };
  return {
    ok: false,
    reason: existing.human_status
      ? `It was changed meanwhile to ${existing.human_status} by ${existing.human_by}. Nothing saved; reload and try again.`
      : "Its decision was cleared meanwhile. Nothing saved; reload and try again.",
  };
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
