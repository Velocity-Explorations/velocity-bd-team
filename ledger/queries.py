"""The ledger's query functions. Every component talks to the database through these.

Conventions:
- Every function opens its own transaction; callers never pass connections.
- Timestamps are ISO-8601 UTC text (see ledger.db.now_iso).
- JSON columns (stage_counts, matched_keywords, extra, themes, payload, preview) accept a
  dict/list and are stored as JSON text; they come back as text.
"""
from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ledger.db import now_iso, one, q, rows, tx

# Columns a portal adapter is allowed to write. Everything else on `calls` belongs to a
# downstream component and is never touched by upsert_call.
SCRAPED_COLUMNS = [
    "portal", "title", "type", "department", "naics_code", "set_aside",
    "posted_date", "due_date", "description", "url", "source_type", "extra",
]

PROPOSAL_COLUMNS = [
    "title", "portal", "agency", "solicitation_id", "type", "role", "partners",
    "submitted_date", "due_date", "requested_value", "outcome", "outcome_date",
    "award_value", "strength_rating", "strength_reason", "why_won_or_lost",
    "use_as_exemplar", "themes", "drive_link", "brief",
]


def _jsonify(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _placeholders(n: int) -> str:
    return ", ".join(["?"] * n)


# ----------------------------------------------------------------------------- runs

def start_run(portal: str | None, dry_run: bool = False, component: str | None = None) -> int:
    """Insert a 'running' row and return its id. component defaults to the portal slug."""
    with tx() as conn:
        cur = q(
            conn,
            "INSERT INTO runs (component, portal, started_at, status, dry_run) "
            "VALUES (?, ?, ?, 'running', ?) RETURNING id",
            (component or portal or "pipeline", portal, now_iso(), 1 if dry_run else 0),
        )
        return int(cur.fetchone()[0])


def finish_run(
    run_id: int,
    status: str,
    stage_counts: Mapping[str, int] | str | None,
    error: str | None = None,
    log_path: str | Path | None = None,
) -> None:
    with tx() as conn:
        q(
            conn,
            "UPDATE runs SET finished_at = ?, status = ?, stage_counts = ?, error = ?, log_path = ? WHERE id = ?",
            (now_iso(), status, _jsonify(stage_counts), error, str(log_path) if log_path else None, run_id),
        )


def latest_run_id(portal: str | None = None, component: str | None = None) -> int | None:
    """Id of the most recent run, optionally for one portal or component."""
    clauses: list[str] = []
    params: list[Any] = []
    if portal is not None:
        clauses.append("portal = ?")
        params.append(portal)
    if component is not None:
        clauses.append("component = ?")
        params.append(component)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with tx() as conn:
        row = one(q(conn, f"SELECT id FROM runs{where} ORDER BY id DESC LIMIT 1", params))
        return int(row["id"]) if row else None


def recent_runs(component: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
    """Newest runs first, optionally for one component (a portal's slug, "slack", ...)."""
    where = " WHERE component = ?" if component else ""
    params: list[Any] = [component] if component else []
    with tx() as conn:
        return rows(q(conn, f"SELECT * FROM runs{where} ORDER BY id DESC LIMIT ?", [*params, limit]))


def get_run(run_id: int) -> dict[str, Any] | None:
    with tx() as conn:
        return one(q(conn, "SELECT * FROM runs WHERE id = ?", (run_id,)))


# ---------------------------------------------------------------------------- calls

def upsert_call(record: Mapping[str, Any], run_id: int) -> bool:
    """Insert a scraped call or refresh its scraped fields. Returns True when the id is new.

    On update only the keys present in ``record`` (restricted to SCRAPED_COLUMNS) plus
    last_seen_at / last_run_id / updated_at change. filter_*, ai_*, slack_* and human_*
    columns are never written here.
    """
    rec = {k: _jsonify(v) for k, v in record.items()}
    call_id = rec["id"]
    now = now_iso()
    with tx() as conn:
        exists = one(q(conn, "SELECT 1 AS x FROM calls WHERE id = ?", (call_id,)))
        if exists is None:
            cols = ["id", *SCRAPED_COLUMNS, "first_seen_at", "last_seen_at", "first_run_id", "last_run_id", "updated_at"]
            vals = [call_id, *(rec.get(c) for c in SCRAPED_COLUMNS), now, now, run_id, run_id, now]
            q(conn, f"INSERT INTO calls ({', '.join(cols)}) VALUES ({_placeholders(len(cols))})", vals)
            return True
        present = [c for c in SCRAPED_COLUMNS if c in rec]
        sets = "".join(f"{c} = ?, " for c in present)
        vals = [*(rec[c] for c in present), now, run_id, now, call_id]
        q(conn, f"UPDATE calls SET {sets}last_seen_at = ?, last_run_id = ?, updated_at = ? WHERE id = ?", vals)
        return False


def get_call(call_id: str) -> dict[str, Any] | None:
    with tx() as conn:
        return one(q(conn, "SELECT * FROM calls WHERE id = ?", (call_id,)))


def set_filter(
    call_id: str,
    result: str,
    reason: str | None = None,
    tier: str | None = None,
    keywords: list[str] | None = None,
) -> None:
    with tx() as conn:
        q(
            conn,
            "UPDATE calls SET filter_result = ?, filter_reason = ?, match_tier = ?, matched_keywords = ?, "
            "updated_at = ? WHERE id = ?",
            (result, reason, tier, _jsonify(keywords), now_iso(), call_id),
        )


def set_review(call_id: str, verdict: str, reasoning: str | None) -> None:
    now = now_iso()
    with tx() as conn:
        q(
            conn,
            "UPDATE calls SET ai_verdict = ?, ai_reasoning = ?, reviewed_at = ?, updated_at = ? WHERE id = ?",
            (verdict, reasoning, now, now, call_id),
        )


def set_slack(call_id: str, channel: str, ts: str) -> None:
    now = now_iso()
    with tx() as conn:
        q(
            conn,
            "UPDATE calls SET slack_channel = ?, slack_ts = ?, posted_at = ?, updated_at = ? WHERE id = ?",
            (channel, ts, now, now, call_id),
        )


def set_human(call_id: str, status: str, by: str, at: str | None = None) -> None:
    """Record a person's decision. It becomes the call's current decision (calls.human_*) and is
    added to the call's history in `decisions`, so an earlier decision by someone else is kept."""
    at = at or now_iso()
    with tx() as conn:
        cur = q(
            conn,
            "UPDATE calls SET human_status = ?, human_by = ?, human_at = ?, updated_at = ? WHERE id = ?",
            (status, by, at, now_iso(), call_id),
        )
        if cur.rowcount == 1:
            q(conn, "INSERT INTO decisions (call_id, decided_by, status, decided_at) VALUES (?, ?, ?, ?)",
              (call_id, by, status, at))


def append_note(call_id: str, text: str, by: str, at: str | None = None) -> str:
    """Append '[at by] text' as a new line on human_notes. Returns the full notes."""
    line = f"[{at or now_iso()} {by}] {text}"
    with tx() as conn:
        row = one(q(conn, "SELECT human_notes FROM calls WHERE id = ?", (call_id,)))
        if row is None:
            raise KeyError(f"no call with id {call_id}")
        notes = f"{row['human_notes']}\n{line}" if row["human_notes"] else line
        q(conn, "UPDATE calls SET human_notes = ?, updated_at = ? WHERE id = ?", (notes, now_iso(), call_id))
        return notes


def calls_for_review(run_id: int) -> list[dict[str, Any]]:
    """Calls seen in this run that passed the filter and have no AI verdict yet."""
    with tx() as conn:
        return rows(q(
            conn,
            "SELECT * FROM calls WHERE last_run_id = ? AND filter_result = 'kept' AND ai_verdict IS NULL "
            "ORDER BY first_seen_at, id",
            (run_id,),
        ))


def calls_where(
    portal: str | None = None,
    filter_result: str | None = None,
    reviewed: bool | None = None,
) -> list[dict[str, Any]]:
    """All calls, narrowed by portal, filter_result ('pending', 'kept', 'rejected') and/or
    whether an AI verdict exists (reviewed=False means ai_verdict IS NULL)."""
    clauses: list[str] = []
    params: list[Any] = []
    if portal is not None:
        clauses.append("portal = ?")
        params.append(portal)
    if filter_result is not None:
        clauses.append("filter_result = ?")
        params.append(filter_result)
    if reviewed is True:
        clauses.append("ai_verdict IS NOT NULL")
    elif reviewed is False:
        clauses.append("ai_verdict IS NULL")
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with tx() as conn:
        return rows(q(conn, f"SELECT * FROM calls{where} ORDER BY first_seen_at, id", params))


def calls_in_run(run_id: int) -> list[dict[str, Any]]:
    """Every call seen (inserted or refreshed) by this run."""
    with tx() as conn:
        return rows(q(conn, "SELECT * FROM calls WHERE last_run_id = ? ORDER BY first_seen_at, id", (run_id,)))


def new_calls(run_id: int) -> list[dict[str, Any]]:
    """Calls first seen in this run whose verdict is yes or maybe: what gets posted to Slack."""
    with tx() as conn:
        return rows(q(
            conn,
            "SELECT * FROM calls WHERE first_run_id = ? AND ai_verdict IN ('yes', 'maybe') ORDER BY first_seen_at, id",
            (run_id,),
        ))


def pending_feedback() -> list[dict[str, Any]]:
    """Posted to Slack, no human decision yet."""
    with tx() as conn:
        return rows(q(
            conn,
            "SELECT * FROM calls WHERE slack_ts IS NOT NULL AND human_status IS NULL ORDER BY posted_at, id",
        ))


def recent_decisions(limit: int = 20) -> list[dict[str, Any]]:
    """Calls with a human decision, newest decision first."""
    with tx() as conn:
        return rows(q(
            conn,
            "SELECT * FROM calls WHERE human_status IS NOT NULL ORDER BY human_at DESC, updated_at DESC, id LIMIT ?",
            (limit,),
        ))


def export_csv(path: str | Path) -> int:
    """Write every calls row to a UTF-8 CSV. Returns the row count."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    with tx() as conn:
        data = rows(q(conn, "SELECT * FROM calls ORDER BY first_seen_at, id"))
    with target.open("w", newline="", encoding="utf-8") as fh:
        if data:
            writer = csv.DictWriter(fh, fieldnames=list(data[0].keys()))
            writer.writeheader()
            writer.writerows(data)
    return len(data)


# ------------------------------------------------------------------------ proposals

def upsert_proposal(row: Mapping[str, Any]) -> bool:
    """Insert or update a past submission by submission_id. Returns True when new."""
    rec = {k: _jsonify(v) for k, v in row.items()}
    sid = rec["submission_id"]
    now = now_iso()
    present = [c for c in PROPOSAL_COLUMNS if c in rec]
    with tx() as conn:
        exists = one(q(conn, "SELECT 1 AS x FROM proposals WHERE submission_id = ?", (sid,)))
        if exists is None:
            cols = ["submission_id", *present, "synced_at", "updated_at"]
            vals = [sid, *(rec[c] for c in present), now, now]
            q(conn, f"INSERT INTO proposals ({', '.join(cols)}) VALUES ({_placeholders(len(cols))})", vals)
            return True
        sets = "".join(f"{c} = ?, " for c in present)
        vals = [*(rec[c] for c in present), now, now, sid]
        q(conn, f"UPDATE proposals SET {sets}synced_at = ?, updated_at = ? WHERE submission_id = ?", vals)
        return False


def list_proposals(portal: str | None = None, outcome: str | None = None) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if portal is not None:
        clauses.append("portal = ?")
        params.append(portal)
    if outcome is not None:
        clauses.append("outcome = ?")
        params.append(outcome)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    with tx() as conn:
        return rows(q(conn, f"SELECT * FROM proposals{where} ORDER BY submitted_date DESC, submission_id", params))


# ------------------------------------------------------------------ change requests
# The assistant's approval queue (docs/ASSISTANT.md). Every status change is guarded by the
# status it expects, so a request is decided once and carried out once.

REQUEST_KINDS = ("keyword_change", "rereview", "scan", "draft", "fault_report")
REQUEST_OUTCOMES = ("applied", "failed")
OPEN_REQUEST_STATUSES = ("proposed", "approved", "applying")


def _request_json(value: Any) -> str | None:
    """Payloads and previews as JSON text with sorted keys, so equal payloads compare equal."""
    return None if value is None else json.dumps(value, ensure_ascii=False, sort_keys=True)


def create_request(
    kind: str,
    summary: str,
    requested_by: str,
    *,
    portal: str | None = None,
    call_id: str | None = None,
    reason: str | None = None,
    payload: Any = None,
    preview: Any = None,
) -> int:
    """Record a proposed change request. Returns its id."""
    if kind not in REQUEST_KINDS:
        raise ValueError(f"unknown request kind: {kind}")
    now = now_iso()
    with tx() as conn:
        cur = q(
            conn,
            "INSERT INTO change_requests (kind, portal, call_id, summary, reason, payload, preview, status, "
            "requested_by, requested_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, 'proposed', ?, ?, ?) RETURNING id",
            (kind, portal, call_id, summary, reason or None, _request_json(payload), _request_json(preview),
             requested_by, now, now),
        )
        return int(cur.fetchone()[0])


def get_request(request_id: int) -> dict[str, Any] | None:
    with tx() as conn:
        return one(q(conn, "SELECT * FROM change_requests WHERE id = ?", (request_id,)))


def list_requests(
    statuses: str | Sequence[str] | None = None,
    limit: int = 50,
    oldest_first: bool = False,
) -> list[dict[str, Any]]:
    """Requests, newest first (or oldest first), optionally with one of the given statuses."""
    wanted = (statuses,) if isinstance(statuses, str) else tuple(statuses or ())
    where = f" WHERE status IN ({_placeholders(len(wanted))})" if wanted else ""
    order = "ASC" if oldest_first else "DESC"
    with tx() as conn:
        return rows(q(conn, f"SELECT * FROM change_requests{where} ORDER BY id {order} LIMIT ?", [*wanted, limit]))


def count_requests(status: str) -> int:
    with tx() as conn:
        row = one(q(conn, "SELECT COUNT(*) AS n FROM change_requests WHERE status = ?", (status,)))
        return int(row["n"]) if row else 0


def find_open_request(kind: str, portal: str | None, call_id: str | None, payload: Any) -> dict[str, Any] | None:
    """An open request (proposed, approved or applying) asking for exactly the same thing."""
    clauses = ["kind = ?", f"status IN ({_placeholders(len(OPEN_REQUEST_STATUSES))})"]
    params: list[Any] = [kind, *OPEN_REQUEST_STATUSES]
    for column, value in (("portal", portal), ("call_id", call_id), ("payload", _request_json(payload))):
        if value is None:
            clauses.append(f"{column} IS NULL")
        else:
            clauses.append(f"{column} = ?")
            params.append(value)
    with tx() as conn:
        return one(q(conn, f"SELECT * FROM change_requests WHERE {' AND '.join(clauses)} ORDER BY id LIMIT 1", params))


def decide_request(request_id: int, approve: bool, by: str, note: str | None = None) -> bool:
    """Approve or reject a proposed request. False when it was not waiting for a decision."""
    now = now_iso()
    with tx() as conn:
        cur = q(
            conn,
            "UPDATE change_requests SET status = ?, decided_by = ?, decided_at = ?, decision_note = ?, updated_at = ? "
            "WHERE id = ? AND status = 'proposed'",
            ("approved" if approve else "rejected", by, now, note or None, now, request_id),
        )
        return cur.rowcount == 1


def _move_request(request_id: int, expected: str, status: str, result: str | None) -> bool:
    now = now_iso()
    applied_at = now if status == "applied" else None
    with tx() as conn:
        cur = q(
            conn,
            "UPDATE change_requests SET status = ?, result = COALESCE(?, result), "
            "applied_at = COALESCE(?, applied_at), updated_at = ? WHERE id = ? AND status = ?",
            (status, result, applied_at, now, request_id, expected),
        )
        return cur.rowcount == 1


def claim_request(request_id: int) -> bool:
    """approved -> applying. False when someone else claimed it first, or it is not approved."""
    return _move_request(request_id, "approved", "applying", None)


def release_request(request_id: int, result: str) -> bool:
    """applying -> approved, with a note saying what it is waiting for."""
    return _move_request(request_id, "applying", "approved", result)


def finish_request(request_id: int, status: str, result: str) -> bool:
    """applying -> applied or failed, with what happened."""
    if status not in REQUEST_OUTCOMES:
        raise ValueError(f"finish_request takes applied or failed, not {status}")
    return _move_request(request_id, "applying", status, result)


def note_request(request_id: int, result: str) -> bool:
    """Update an approved request's note (what it is waiting for) without changing its status."""
    with tx() as conn:
        cur = q(conn, "UPDATE change_requests SET result = ?, updated_at = ? WHERE id = ? AND status = 'approved'",
                (result, now_iso(), request_id))
        return cur.rowcount == 1


# --------------------------------------------------------------------------------- judgments
# Each judge's verdict on each call (migration 003). calls.ai_verdict stays the Claude review's
# and decides what is posted; these rows let the judges be compared.

def add_judgment(call_id: str, judge: str, model: str, verdict: str, reasoning: str | None,
                 rated_at: str | None = None) -> None:
    """Record one judge's verdict on a call. A newer row for the same call and judge supersedes older ones."""
    with tx() as conn:
        q(conn, "INSERT INTO judgments (call_id, judge, model, verdict, reasoning, rated_at) VALUES (?, ?, ?, ?, ?, ?)",
          (call_id, judge, model, verdict, reasoning, rated_at or now_iso()))


def latest_judgments(call_id: str) -> dict[str, dict[str, Any]]:
    """The newest judgment from each judge on one call, keyed by judge."""
    with tx() as conn:
        found = rows(q(conn, "SELECT judge, model, verdict, reasoning, rated_at FROM judgments "
                             "WHERE call_id = ? ORDER BY id", (call_id,)))
    return {row["judge"]: row for row in found}


# The judge scoreboard, also in docs/LEDGER_SCHEMA.md ("Judge scoreboard"). The team's decision is
# calls.human_status; pursue and submitted mean yes, not_relevant and dismissed mean no. A judge's
# verdict counts only if it was given before the call's first decision, because decided calls are
# among the examples in the judges' prompt.
JUDGE_RECORDS_SQL = """
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
"""


def calls_without_judgment(judge: str) -> list[dict[str, Any]]:
    """Kept, reviewed calls this judge has not rated yet, oldest first."""
    with tx() as conn:
        return rows(q(conn, "SELECT * FROM calls WHERE filter_result = 'kept' AND ai_verdict IS NOT NULL "
                            "AND NOT EXISTS (SELECT 1 FROM judgments AS j WHERE j.call_id = calls.id AND j.judge = ?) "
                            "ORDER BY first_seen_at, id", (judge,)))


def judge_records() -> list[dict[str, Any]]:
    """Each judge against the team's decisions: calls it judged before they were decided, matches,
    misses (it said no, the team pursued) and false alarms (it said yes, the team passed)."""
    with tx() as conn:
        return rows(q(conn, JUDGE_RECORDS_SQL))


# --------------------------------------------------------------------------------- decisions
# Every decision on every call, kept per person (migration 004). calls.human_status is the
# latest of them, the team's current decision.

def decision_history(call_id: str) -> list[dict[str, Any]]:
    """Every decision on one call, oldest first: who decided, what, when, and any note."""
    with tx() as conn:
        return rows(q(conn, "SELECT decided_by, status, note, decided_at FROM decisions WHERE call_id = ? ORDER BY id",
                      (call_id,)))


# ------------------------------------------------------------------------------ briefs
# The Monday brief, kept per week for the dashboard (migration 005): one row per portal and one
# with no portal for the Top 10 across portals. A newer row for the same week and portal replaces it.

def save_brief(week_of: str, portal: str | None, body: Mapping[str, Any], written_by: str) -> None:
    """Store one part of a week's brief, replacing what that week already held for the portal."""
    with tx() as conn:
        if portal is None:
            q(conn, "DELETE FROM briefs WHERE week_of = ? AND portal IS NULL", (week_of,))
        else:
            q(conn, "DELETE FROM briefs WHERE week_of = ? AND portal = ?", (week_of, portal))
        q(conn, "INSERT INTO briefs (week_of, portal, body, written_by, created_at) VALUES (?, ?, ?, ?, ?)",
          (week_of, portal, json.dumps(dict(body), ensure_ascii=False), written_by, now_iso()))


def briefs_for_week(week_of: str) -> list[dict[str, Any]]:
    """A week's brief rows in the order they were written; `body` is JSON text."""
    with tx() as conn:
        return rows(q(conn, "SELECT id, week_of, portal, body, written_by, created_at FROM briefs "
                            "WHERE week_of = ? ORDER BY id", (week_of,)))


def brief_weeks(limit: int = 52) -> list[str]:
    """The weeks that have a brief, newest first."""
    with tx() as conn:
        found = rows(q(conn, "SELECT DISTINCT week_of FROM briefs ORDER BY week_of DESC LIMIT ?", (limit,)))
    return [r["week_of"] for r in found]
