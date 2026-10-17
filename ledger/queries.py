"""The ledger's query functions. Every component talks to the database through these.

Conventions:
- Every function opens its own transaction; callers never pass connections.
- Timestamps are ISO-8601 UTC text (see ledger.db.now_iso).
- JSON columns (stage_counts, matched_keywords, extra, themes) accept a dict/list and are
  stored as JSON text; they come back as text.
"""
from __future__ import annotations

import csv
import json
from collections.abc import Mapping
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
    with tx() as conn:
        q(
            conn,
            "UPDATE calls SET human_status = ?, human_by = ?, human_at = ?, updated_at = ? WHERE id = ?",
            (status, by, at or now_iso(), now_iso(), call_id),
        )


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
