"""The ledger's query functions. Every component talks to the database through these.

Conventions:
- Every function opens its own transaction; callers never pass connections.
- Timestamps are ISO-8601 UTC text (see ledger.db.now_iso).
- JSON columns (stage_counts, matched_keywords, extra, themes, payload, preview, and the
  workspace's collaborators, builds_on, files, content, task_states) accept a dict/list and are
  stored as JSON text; they come back as text.
"""
from __future__ import annotations

import csv
import json
from collections.abc import Mapping, Sequence
from datetime import date
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


def sam_notices_on(portal: str, key: str) -> dict[str, str]:
    """SAM.gov notice ids that a portal's calls carry in extra[key], each with its call id.
    SSC Front Door reposts SAM.gov notices; the SAM.gov adapter skips those (PRO-525)."""
    with tx() as conn:
        found = rows(q(conn, "SELECT id, extra FROM calls WHERE portal = ?", (portal,)))
    notices: dict[str, str] = {}
    for row in found:
        try:
            extra = json.loads(row["extra"] or "{}")
        except (TypeError, ValueError):
            continue
        notice = extra.get(key) if isinstance(extra, dict) else None
        if notice:
            notices[str(notice).lower()] = row["id"]
    return notices


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


# --------------------------------------------------------------------------------- tags
# Tags from the set list in review/tags.yaml on each call (migration 006), kept per source: "rule"
# for what the call's own data makes certain, "claude" and "grok" for each judge's picks.

def set_tags(call_id: str, source: str, tags: Sequence[str]) -> None:
    """Replace one source's tags on a call; the other sources' tags stay."""
    now = now_iso()
    with tx() as conn:
        q(conn, "DELETE FROM call_tags WHERE call_id = ? AND source = ?", (call_id, source))
        for tag in dict.fromkeys(tags):
            q(conn, "INSERT INTO call_tags (call_id, tag, source, tagged_at) VALUES (?, ?, ?, ?)",
              (call_id, tag, source, now))


def tags_on(call_id: str) -> dict[str, list[str]]:
    """One call's tags by source, each in the order it was set."""
    with tx() as conn:
        found = rows(q(conn, "SELECT tag, source FROM call_tags WHERE call_id = ? ORDER BY id", (call_id,)))
    by_source: dict[str, list[str]] = {}
    for row in found:
        by_source.setdefault(row["source"], []).append(row["tag"])
    return by_source


def save_tag_list(entries: Sequence[tuple[str, str, str]]) -> None:
    """Rewrite the tag list (migration 007) as (name, group, what it covers), in the list's order."""
    with tx() as conn:
        q(conn, "DELETE FROM tag_list")
        for position, (name, group, covers) in enumerate(entries):
            q(conn, "INSERT INTO tag_list (name, tag_group, covers, position) VALUES (?, ?, ?, ?)",
              (name, group, covers or None, position))


def tag_catalog() -> list[dict[str, Any]]:
    """The tag list as the dashboard reads it, in order."""
    with tx() as conn:
        return rows(q(conn, "SELECT name, tag_group, covers, position FROM tag_list ORDER BY position"))


def calls_without_tags(source: str) -> list[dict[str, Any]]:
    """Kept, reviewed calls with no tags from this judge yet, oldest first."""
    with tx() as conn:
        return rows(q(conn, "SELECT * FROM calls WHERE filter_result = 'kept' AND ai_verdict IS NOT NULL "
                            "AND NOT EXISTS (SELECT 1 FROM call_tags AS t WHERE t.call_id = calls.id AND t.source = ?) "
                            "ORDER BY first_seen_at, id", (source,)))


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


# ------------------------------------------------------------------------------ pursuits
# The proposal workspace (migration 008). A pursuit is one call being drafted, at most one per
# call, and each attempt at a step is a pursuit_steps row. The worker claims queued rows and saves
# its work (ready); the owner approves (the next step is queued), asks for changes (a new attempt
# with the note), retries a failed or blocked attempt, or stops. Every change is guarded by the
# state it expects, so the owner and the worker never both win. Who may decide (only the owner,
# PW17) is the dashboard's check; these record who did.

STEPS = ("discovery", "summary", "alignment", "requirements", "go_no_go", "outline", "draft", "compliance",
         "reviews", "final", "submit")
STEP_LABELS = {
    "discovery": "Discovery", "summary": "Opportunity summary", "alignment": "Alignment",
    "requirements": "Requirements and checklist", "go_no_go": "Go or no-go", "outline": "Outline",
    "draft": "First draft", "compliance": "Compliance check", "reviews": "Reviews", "final": "Final checks",
    "submit": "Submit",
}
KEY_GATES = ("go_no_go", "outline", "submit")     # the owner decides these even with key gates only (PW5)
NO_GO_STEPS = STEPS[:5]                            # Stop here, no-go: steps 1 to 4 and the gate (PW4, PW10)
APPROVAL_MODES = ("every_step", "key_gates")
DEFAULT_BUDGET_USD = 200.0
WORKER = "worker"
AUTO_APPROVER = "worker (key gates only)"
EVENT_KINDS = (
    "started", "step_saved", "approved", "auto_approved", "go", "go_with_conditions", "changes_asked", "retried",
    "failed", "blocked", "stopped", "no_go", "closed", "material", "collaborators", "builds_on", "direction",
    "checklist", "budget", "submitted", "result", "result_date",
)
_LIVE = "pursuit_id IN (SELECT id FROM pursuits WHERE state = 'working')"


class PursuitRefused(ValueError):
    """Start the draft was refused; the message says why, in words for the person."""


def next_step(step: str) -> str | None:
    """The step after this one, or None after Submit."""
    at = STEPS.index(step)
    return STEPS[at + 1] if at + 1 < len(STEPS) else None


def needs_owner(step: str, approval_mode: str) -> bool:
    """Whether the owner approves this step, or the worker may (key gates only, PW5)."""
    return approval_mode == "every_step" or step in KEY_GATES


def _label(step: Mapping[str, Any]) -> str:
    label = STEP_LABELS.get(step["step"], step["step"])
    return label if int(step["attempt"]) == 1 else f"{label} (attempt {step['attempt']})"


def _with_note(text: str, note: str | None) -> str:
    return f"{text}: {note}" if note else text


def _event(conn: Any, pursuit_id: int, who: str, kind: str, text: str, step_id: int | None, at: str) -> None:
    if kind not in EVENT_KINDS:
        raise ValueError(f"unknown event kind: {kind}")
    q(conn, "INSERT INTO pursuit_events (pursuit_id, step_id, at, who, kind, text) VALUES (?, ?, ?, ?, ?, ?)",
      (pursuit_id, step_id, at, who, kind, text))


def _queue_step(conn: Any, pursuit_id: int, step: str, by: str, note: str | None, now: str) -> int:
    """Queue the next attempt at a step for the worker and make it the pursuit's current step."""
    last = one(q(conn, "SELECT MAX(attempt) AS n FROM pursuit_steps WHERE pursuit_id = ? AND step = ?", (pursuit_id, step)))
    attempt = int((last or {}).get("n") or 0) + 1
    cur = q(conn, "INSERT INTO pursuit_steps (pursuit_id, step, attempt, state, requested_by, request_note, queued_at, "
                  "updated_at) VALUES (?, ?, ?, 'queued', ?, ?, ?, ?) RETURNING id",
            (pursuit_id, step, attempt, by, note, now, now))
    step_id = int(cur.fetchone()[0])
    q(conn, "UPDATE pursuits SET current_step = ?, updated_at = ? WHERE id = ?", (step, now, pursuit_id))
    return step_id


def _spend(conn: Any, step_id: int, cost_usd: float, now: str) -> dict[str, Any]:
    """Add what a step cost to its pursuit's total. Returns the step's row."""
    step = one(q(conn, "SELECT * FROM pursuit_steps WHERE id = ?", (step_id,)))
    assert step is not None
    if cost_usd:
        q(conn, "UPDATE pursuits SET cost_usd = cost_usd + ?, updated_at = ? WHERE id = ?", (cost_usd, now, step["pursuit_id"]))
    return step


def start_pursuit(
    call_id: str,
    owner: str,
    *,
    format: str | None = None,
    approval_mode: str = "every_step",
    direction: str | None = None,
    collaborators: Sequence[str] = (),
    builds_on: Sequence[Mapping[str, Any]] = (),
    budget_usd: float = DEFAULT_BUDGET_USD,
) -> int:
    """Start the draft (P6): the pursuit, its Discovery step queued for the worker, and the first line of
    its history. Refused, with the reason, for an unknown call, a call marked Not relevant, or a call
    that already has a draft. Returns the pursuit's id."""
    if approval_mode not in APPROVAL_MODES:
        raise ValueError(f"unknown approval mode: {approval_mode}")
    now = now_iso()
    with tx() as conn:
        call = one(q(conn, "SELECT human_status FROM calls WHERE id = ?", (call_id,)))
        if call is None:
            raise PursuitRefused(f"No call with id {call_id}.")
        if call["human_status"] == "not_relevant":
            raise PursuitRefused("This call is marked Not relevant.")
        held = one(q(conn, "SELECT owner, created_at FROM pursuits WHERE call_id = ?", (call_id,)))
        if held is not None:
            raise PursuitRefused(f"This call already has a draft, started by {held['owner']} on {held['created_at'][:10]}.")
        cur = q(conn, "INSERT INTO pursuits (call_id, owner, collaborators, format, approval_mode, direction, builds_on, "
                      "current_step, state, budget_usd, created_at, updated_at) "
                      "VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'working', ?, ?, ?) RETURNING id",
                (call_id, owner, _jsonify(list(collaborators)) if collaborators else None, format, approval_mode,
                 direction or None, _jsonify([dict(b) for b in builds_on]) if builds_on else None, STEPS[0],
                 budget_usd, now, now))
        pursuit_id = int(cur.fetchone()[0])
        step_id = _queue_step(conn, pursuit_id, STEPS[0], owner, None, now)
        mode = "every step approved" if approval_mode == "every_step" else "key gates only"
        _event(conn, pursuit_id, owner, "started", f"Started the draft: {format or 'format not set'}, {mode}", step_id, now)
        return pursuit_id


def get_pursuit(pursuit_id: int) -> dict[str, Any] | None:
    with tx() as conn:
        return one(q(conn, "SELECT * FROM pursuits WHERE id = ?", (pursuit_id,)))


def pursuit_for_call(call_id: str) -> dict[str, Any] | None:
    with tx() as conn:
        return one(q(conn, "SELECT * FROM pursuits WHERE call_id = ?", (call_id,)))


def list_pursuits(states: Sequence[str] | None = None) -> list[dict[str, Any]]:
    """Pursuits, oldest first, optionally only those in the given states."""
    wanted = tuple(states or ())
    where = f" WHERE state IN ({_placeholders(len(wanted))})" if wanted else ""
    with tx() as conn:
        return rows(q(conn, f"SELECT * FROM pursuits{where} ORDER BY id", wanted))


def get_step(step_id: int) -> dict[str, Any] | None:
    with tx() as conn:
        return one(q(conn, "SELECT * FROM pursuit_steps WHERE id = ?", (step_id,)))


def pursuit_steps(pursuit_id: int) -> list[dict[str, Any]]:
    """Every attempt at every step of a pursuit, oldest first."""
    with tx() as conn:
        return rows(q(conn, "SELECT * FROM pursuit_steps WHERE pursuit_id = ? ORDER BY id", (pursuit_id,)))


def latest_steps(pursuit_id: int) -> dict[str, dict[str, Any]]:
    """The newest attempt at each step the pursuit has reached, keyed by step."""
    return {row["step"]: row for row in pursuit_steps(pursuit_id)}


def claim_next_step() -> dict[str, Any] | None:
    """The worker takes the oldest queued step of a pursuit being worked: queued -> working.
    Returns the step's row, or None when nothing is waiting."""
    with tx() as conn:
        waiting = rows(q(conn, f"SELECT id FROM pursuit_steps WHERE state = 'queued' AND {_LIVE} ORDER BY id LIMIT 5"))
        for row in waiting:
            now = now_iso()
            cur = q(conn, f"UPDATE pursuit_steps SET state = 'working', started_at = ?, updated_at = ? "
                          f"WHERE id = ? AND state = 'queued' AND {_LIVE}", (now, now, row["id"]))
            if cur.rowcount == 1:
                return one(q(conn, "SELECT * FROM pursuit_steps WHERE id = ?", (row["id"],)))
    return None


def set_task_states(step_id: int, states: Mapping[str, str]) -> bool:
    """Discovery's tasks and their states (PW6), updated while the worker works the step."""
    with tx() as conn:
        cur = q(conn, "UPDATE pursuit_steps SET task_states = ?, updated_at = ? WHERE id = ? AND state = 'working'",
                (_jsonify(dict(states)), now_iso(), step_id))
        return cur.rowcount == 1


def finish_step(step_id: int, *, summary: str | None = None, files: Any = None, content: Any = None,
                cost_usd: float = 0.0) -> bool:
    """The worker saved the step's work: working -> ready, with what it cost. False when the step is not
    working, or its pursuit stopped meanwhile; the worker then calls stop_step."""
    now = now_iso()
    with tx() as conn:
        cur = q(conn, f"UPDATE pursuit_steps SET state = 'ready', summary = ?, files = ?, content = ?, error = NULL, "
                      f"cost_usd = cost_usd + ?, finished_at = ?, updated_at = ? WHERE id = ? AND state = 'working' AND {_LIVE}",
                (summary, _jsonify(files), _jsonify(content), cost_usd, now, now, step_id))
        if cur.rowcount != 1:
            return False
        step = _spend(conn, step_id, cost_usd, now)
        _event(conn, step["pursuit_id"], WORKER, "step_saved", f"{_label(step)} saved", step_id, now)
        return True


def fail_step(step_id: int, error: str, cost_usd: float = 0.0) -> bool:
    """The step failed: working -> failed, with the reason in words (PW15) and what it cost."""
    now = now_iso()
    with tx() as conn:
        cur = q(conn, "UPDATE pursuit_steps SET state = 'failed', error = ?, cost_usd = cost_usd + ?, finished_at = ?, "
                      "updated_at = ? WHERE id = ? AND state = 'working'", (error, cost_usd, now, now, step_id))
        if cur.rowcount != 1:
            return False
        step = _spend(conn, step_id, cost_usd, now)
        _event(conn, step["pursuit_id"], WORKER, "failed", f"{_label(step)} failed: {error}", step_id, now)
        return True


def block_step(step_id: int, reason: str, cost_usd: float = 0.0) -> bool:
    """The step cannot run until a person acts, for example budget reached (PW19): queued or working -> blocked,
    with what it cost when the worker stopped it mid-way."""
    now = now_iso()
    with tx() as conn:
        cur = q(conn, "UPDATE pursuit_steps SET state = 'blocked', error = ?, cost_usd = cost_usd + ?, finished_at = ?, "
                      "updated_at = ? WHERE id = ? AND state IN ('queued', 'working')", (reason, cost_usd, now, now, step_id))
        if cur.rowcount != 1:
            return False
        step = _spend(conn, step_id, cost_usd, now)
        _event(conn, step["pursuit_id"], WORKER, "blocked", f"{_label(step)} is waiting: {reason}", step_id, now)
        return True


def stop_step(step_id: int, cost_usd: float = 0.0) -> bool:
    """The worker stops a step whose pursuit stopped while it worked: working -> stopped, with what it cost."""
    now = now_iso()
    with tx() as conn:
        cur = q(conn, "UPDATE pursuit_steps SET state = 'stopped', cost_usd = cost_usd + ?, finished_at = ?, updated_at = ? "
                      "WHERE id = ? AND state = 'working' AND pursuit_id IN (SELECT id FROM pursuits WHERE state <> 'working')",
                (cost_usd, now, now, step_id))
        if cur.rowcount != 1:
            return False
        step = _spend(conn, step_id, cost_usd, now)
        _event(conn, step["pursuit_id"], WORKER, "stopped", f"{_label(step)} stopped", step_id, now)
        return True


def _decision_for(step: str, decision: str | None) -> str:
    """What approving this step records: go or go_with_conditions at the gate, approved elsewhere."""
    if step == "submit":
        raise ValueError("Submit is recorded by Mark submitted, not approved like a step")
    allowed = ("go", "go_with_conditions") if step == "go_no_go" else ("approved",)
    chosen = decision or allowed[0]
    if chosen not in allowed:
        raise ValueError(f"{STEP_LABELS.get(step, step)} takes {' or '.join(allowed)}, not {chosen}")
    return chosen


def _decide(conn: Any, step_id: int, state: str, decision: str, by: str, note: str | None,
            expected_updated_at: str | None, now: str) -> bool:
    """ready -> state, recording the decision. Guarded by the pursuit still being worked and, when the
    form carried it, the step's updated_at (C8's pattern), so a stale form changes nothing."""
    sql = (f"UPDATE pursuit_steps SET state = ?, decision = ?, decided_by = ?, decided_at = ?, decision_note = ?, "
           f"updated_at = ? WHERE id = ? AND state = 'ready' AND {_LIVE}")
    params: list[Any] = [state, decision, by, now, note or None, now, step_id]
    if expected_updated_at is not None:
        sql += " AND updated_at = ?"
        params.append(expected_updated_at)
    return q(conn, sql, params).rowcount == 1


def approve_step(step_id: int, by: str, *, decision: str | None = None, note: str | None = None,
                 expected_updated_at: str | None = None) -> int | None:
    """Approve and continue: ready -> approved, and the next step queued. At the gate the decision is go
    or go_with_conditions (PW10); by AUTO_APPROVER is the worker approving with key gates only (PW5).
    Returns the next step's id, or None when the step was not waiting for this decision."""
    now = now_iso()
    with tx() as conn:
        step = one(q(conn, "SELECT * FROM pursuit_steps WHERE id = ?", (step_id,)))
        if step is None:
            return None
        chosen = _decision_for(step["step"], decision)
        following = next_step(step["step"])
        if following is None or not _decide(conn, step_id, "approved", chosen, by, note, expected_updated_at, now):
            return None
        queued = _queue_step(conn, step["pursuit_id"], following, by, None, now)
        if by == AUTO_APPROVER:
            kind, text = "auto_approved", f"{_label(step)} approved automatically (key gates only)"
        elif chosen == "approved":
            kind, text = "approved", _with_note(f"{_label(step)} approved", note)
        else:
            kind, text = chosen, _with_note("Go" if chosen == "go" else "Go with conditions", note)
        _event(conn, step["pursuit_id"], by, kind, text, step_id, now)
        return queued


def ask_changes(step_id: int, by: str, note: str, *, expected_updated_at: str | None = None) -> int | None:
    """Ask for changes: ready -> changes_asked, and the step queued again as a new attempt carrying the
    note, which the worker puts in its prompt. Returns the new attempt's id, or None when refused."""
    note = (note or "").strip()
    if not note:
        raise ValueError("Ask for changes needs a note saying what to change")
    now = now_iso()
    with tx() as conn:
        step = one(q(conn, "SELECT * FROM pursuit_steps WHERE id = ?", (step_id,)))
        if step is None or not _decide(conn, step_id, "changes_asked", "changes_asked", by, note, expected_updated_at, now):
            return None
        redo = _queue_step(conn, step["pursuit_id"], step["step"], by, note, now)
        _event(conn, step["pursuit_id"], by, "changes_asked", f"Asked for changes to {_label(step)}: {note}", step_id, now)
        return redo


def retry_step(step_id: int, by: str) -> int | None:
    """Retry a failed or blocked attempt (PW15, PW19) as a new one; the old attempt keeps its error.
    Returns the new attempt's id, or None when it was retried already or is not failed or blocked."""
    now = now_iso()
    with tx() as conn:
        cur = q(conn, f"UPDATE pursuit_steps SET decision = 'retried', decided_by = ?, decided_at = ?, updated_at = ? "
                      f"WHERE id = ? AND state IN ('failed', 'blocked') AND decision IS NULL AND {_LIVE}",
                (by, now, now, step_id))
        if cur.rowcount != 1:
            return None
        step = one(q(conn, "SELECT * FROM pursuit_steps WHERE id = ?", (step_id,)))
        assert step is not None
        redo = _queue_step(conn, step["pursuit_id"], step["step"], by, None, now)
        _event(conn, step["pursuit_id"], by, "retried", f"Retried {STEP_LABELS.get(step['step'], step['step'])}", redo, now)
        return redo


def no_go(step_id: int, by: str, note: str, *, expected_updated_at: str | None = None) -> bool:
    """Stop here, no-go (PW4) or No-go at the gate (PW10): the step stops with the note and the pursuit
    becomes no_go. The dashboard records the call as Not relevant through its own guard (P7)."""
    note = (note or "").strip()
    if not note:
        raise ValueError("No-go needs the reason and what would change the answer")
    now = now_iso()
    with tx() as conn:
        step = one(q(conn, "SELECT * FROM pursuit_steps WHERE id = ?", (step_id,)))
        if step is None:
            return False
        if step["step"] not in NO_GO_STEPS:
            raise ValueError(f"no-go is offered on steps 1 to 4 and the gate, not on {STEP_LABELS.get(step['step'], step['step'])}")
        if not _decide(conn, step_id, "stopped", "no_go", by, note, expected_updated_at, now):
            return False
        q(conn, "UPDATE pursuits SET state = 'no_go', updated_at = ? WHERE id = ? AND state = 'working'", (now, step["pursuit_id"]))
        _event(conn, step["pursuit_id"], by, "no_go", f"No-go at {_label(step)}: {note}", step_id, now)
        return True


def close_pursuit(pursuit_id: int, by: str, note: str | None = None) -> bool:
    """Close a pursuit being worked. Steps waiting for the worker or the owner stop at once; a working
    step is left to the worker, which stops it at its next phase boundary (stop_step)."""
    now = now_iso()
    with tx() as conn:
        cur = q(conn, "UPDATE pursuits SET state = 'closed', updated_at = ? WHERE id = ? AND state = 'working'", (now, pursuit_id))
        if cur.rowcount != 1:
            return False
        q(conn, "UPDATE pursuit_steps SET state = 'stopped', updated_at = ? "
                "WHERE pursuit_id = ? AND state IN ('queued', 'ready', 'blocked')", (now, pursuit_id))
        _event(conn, pursuit_id, by, "closed", _with_note("Closed", note), None, now)
        return True


def add_event(pursuit_id: int, who: str, kind: str, text: str, step_id: int | None = None) -> None:
    """Add a line to a pursuit's history (PW16), for example material someone added."""
    with tx() as conn:
        _event(conn, pursuit_id, who, kind, text, step_id, now_iso())


def pursuit_events(pursuit_id: int) -> list[dict[str, Any]]:
    """A pursuit's history, oldest first."""
    with tx() as conn:
        return rows(q(conn, "SELECT * FROM pursuit_events WHERE pursuit_id = ? ORDER BY id", (pursuit_id,)))


# ------------------------------------------------------------------------------ the worker
# The Writer's worker (drafting/worker.py, PRO-577): its heartbeat, which tells the dashboard drafting
# is set up (P8); what Discovery and Requirements and checklist leave on the pursuit; and the facts
# Discovery's clash check reads.

WORKER_STATES = ("idle", "working", "stopped")
CHECKLIST_PARTS = ("registrations", "documents", "inputs", "formatting", "reviews", "submission")
CHECKLIST_ORIGINS = ("requirements", "condition")


def _iso_date(value: str) -> str:
    """A YYYY-MM-DD date, or ValueError."""
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError(f"not a YYYY-MM-DD date: {value!r}")
    return date.fromisoformat(value).isoformat()


def worker_started(name: str) -> None:
    """The worker started: seen now, idle."""
    now = now_iso()
    with tx() as conn:
        q(conn, "INSERT INTO workers (name, started_at, seen_at, state, doing) VALUES (?, ?, ?, 'idle', NULL) "
                "ON CONFLICT (name) DO UPDATE SET started_at = excluded.started_at, seen_at = excluded.seen_at, "
                "state = 'idle', doing = NULL", (name, now, now))


def worker_beat(name: str, state: str, doing: str | None = None) -> None:
    """The worker's heartbeat: seen now, idle, working on something (said in words), or stopped."""
    if state not in WORKER_STATES:
        raise ValueError(f"unknown worker state: {state}")
    now = now_iso()
    with tx() as conn:
        q(conn, "INSERT INTO workers (name, started_at, seen_at, state, doing) VALUES (?, ?, ?, ?, ?) "
                "ON CONFLICT (name) DO UPDATE SET seen_at = excluded.seen_at, state = excluded.state, doing = excluded.doing",
          (name, now, now, state, doing))


def get_worker(name: str) -> dict[str, Any] | None:
    with tx() as conn:
        return one(q(conn, "SELECT * FROM workers WHERE name = ?", (name,)))


def steps_in_state(state: str) -> list[dict[str, Any]]:
    """Every attempt in one state, oldest first. At start the worker fails any left working (PW15)."""
    with tx() as conn:
        return rows(q(conn, "SELECT * FROM pursuit_steps WHERE state = ? ORDER BY id", (state,)))


def set_result_expected(pursuit_id: int, expected_by: str, source: str) -> bool:
    """When the result is expected (P4) and where that came from, from Discovery."""
    expected_by = _iso_date(expected_by)
    with tx() as conn:
        cur = q(conn, "UPDATE pursuits SET result_expected_by = ?, result_expected_source = ?, updated_at = ? "
                      "WHERE id = ? AND state = 'working'", (expected_by, source, now_iso(), pursuit_id))
        return cur.rowcount == 1


def set_target_dates(pursuit_id: int, dates: Mapping[str, str]) -> bool:
    """Each step's target date and the internal submit-by date (PW9, PW18), from Requirements and checklist."""
    checked = {str(key): _iso_date(value) for key, value in dates.items()}
    with tx() as conn:
        cur = q(conn, "UPDATE pursuits SET target_dates = ?, updated_at = ? WHERE id = ? AND state = 'working'",
                (_jsonify(checked), now_iso(), pursuit_id))
        return cur.rowcount == 1


def save_checklist(pursuit_id: int, items: Sequence[Mapping[str, Any]], origin: str) -> int:
    """The submission checklist (PW9) as rows, in the order given. Items already met start ticked by the
    worker. A redo replaces the open items of the same origin and keeps the ticked ones, each in its new
    place when it is listed again, so nothing ticked is lost or repeated. Returns the rows added."""
    if origin not in CHECKLIST_ORIGINS:
        raise ValueError(f"unknown checklist origin: {origin}")
    for item in items:
        if item.get("part") not in CHECKLIST_PARTS:
            raise ValueError(f"unknown checklist part: {item.get('part')!r}")
        if not str(item.get("text") or "").strip():
            raise ValueError("a checklist item needs its text")
    now = now_iso()
    added = 0
    with tx() as conn:
        q(conn, "DELETE FROM checklist_items WHERE pursuit_id = ? AND origin = ? AND done = 0", (pursuit_id, origin))
        kept = {r["text"]: r["id"] for r in rows(q(conn, "SELECT id, text FROM checklist_items WHERE pursuit_id = ? "
                                                         "AND origin = ? ORDER BY position, id", (pursuit_id, origin)))}
        for position, item in enumerate(items):
            text = str(item["text"]).strip()
            if text in kept:
                q(conn, "UPDATE checklist_items SET position = ?, updated_at = ? WHERE id = ?", (position, now, kept.pop(text)))
                continue
            done = bool(item.get("done"))
            due = item.get("due_date")
            q(conn, "INSERT INTO checklist_items (pursuit_id, part, position, text, source, owner, due_date, origin, done, "
                    "done_by, done_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
              (pursuit_id, item["part"], position, text, item.get("source") or None, item.get("owner") or None,
               _iso_date(due) if due else None, origin, 1 if done else 0, WORKER if done else None,
               now if done else None, now, now))
            added += 1
        for extra, item_id in enumerate(kept.values(), start=len(items)):
            q(conn, "UPDATE checklist_items SET position = ?, updated_at = ? WHERE id = ?", (extra, now, item_id))
    return added


def checklist(pursuit_id: int) -> list[dict[str, Any]]:
    """A pursuit's checklist in order."""
    with tx() as conn:
        return rows(q(conn, "SELECT * FROM checklist_items WHERE pursuit_id = ? ORDER BY position, id", (pursuit_id,)))


def calls_titled(title: str, exclude_id: str | None = None) -> list[dict[str, Any]]:
    """Calls with the same title, ignoring case and spaces at the ends: the same call on another portal."""
    with tx() as conn:
        return rows(q(conn, "SELECT id, portal, title, due_date, url, human_status FROM calls "
                            "WHERE LOWER(TRIM(title)) = LOWER(TRIM(?)) AND id <> ? ORDER BY id", (title, exclude_id or "")))


def pursued_calls(exclude_id: str | None = None) -> list[dict[str, Any]]:
    """Calls marked Pursue, for Discovery's check on other pursued calls closing near the same date."""
    with tx() as conn:
        return rows(q(conn, "SELECT id, portal, title, due_date FROM calls WHERE human_status = 'pursue' AND id <> ? "
                            "ORDER BY id", (exclude_id or "",)))
