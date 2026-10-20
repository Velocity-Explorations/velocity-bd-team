"""Every decision is kept per person (migration 004), and the judges are scored against the team's."""
from __future__ import annotations

from pathlib import Path

from ledger import queries as lq
from ledger.db import q, tx

MIGRATION = Path(__file__).resolve().parent.parent / "ledger" / "migrations" / "004_decisions.sql"


def seed(call_id: str) -> None:
    run = lq.start_run("Fake")
    lq.upsert_call({"id": call_id, "portal": "Fake", "title": call_id}, run)


def test_each_decision_is_kept_with_who_made_it(ledger_db: str) -> None:
    seed("c-1")
    lq.set_human("c-1", "pursue", "David Wood", at="2026-10-20T10:00:00Z")
    lq.set_human("c-1", "dismissed", "Shaun Jones", at="2026-10-20T11:00:00Z")
    assert [(d["decided_by"], d["status"]) for d in lq.decision_history("c-1")] == [
        ("David Wood", "pursue"), ("Shaun Jones", "dismissed")]
    assert lq.get_call("c-1")["human_status"] == "dismissed"   # type: ignore[index]   the team's decision is the latest


def test_the_migration_copies_decisions_made_before_it(ledger_db: str) -> None:
    seed("c-old")
    with tx() as conn:   # a decision written before migration 004 existed, so it has no history row
        q(conn, "UPDATE calls SET human_status = 'pursue', human_by = 'U08V7ULPH1N', "
                "human_at = '2026-10-16T18:00:00Z' WHERE id = 'c-old'")
    insert = next(s for s in MIGRATION.read_text(encoding="utf-8").split(";") if "INSERT INTO decisions" in s)
    with tx() as conn:
        q(conn, insert)
    assert [(d["decided_by"], d["status"], d["decided_at"]) for d in lq.decision_history("c-old")] == [
        ("U08V7ULPH1N", "pursue", "2026-10-16T18:00:00Z")]


def test_judge_records_count_only_verdicts_given_before_the_decision(ledger_db: str) -> None:
    for call_id in ("a", "b", "c", "d"):
        seed(call_id)
    lq.add_judgment("a", "claude", "m", "yes", "r", rated_at="2026-10-16T10:00:00Z")   # pursued: match
    lq.add_judgment("a", "grok", "m", "no", "r", rated_at="2026-10-16T10:00:00Z")      # pursued: miss
    lq.set_human("a", "pursue", "David Wood", at="2026-10-17T10:00:00Z")
    lq.add_judgment("b", "claude", "m", "yes", "r", rated_at="2026-10-16T10:00:00Z")   # dismissed: false alarm
    lq.set_human("b", "dismissed", "Shaun Jones", at="2026-10-17T10:00:00Z")
    lq.add_judgment("b", "grok", "m", "no", "r", rated_at="2026-10-20T10:00:00Z")      # after the decision: ignored
    lq.add_judgment("c", "claude", "m", "maybe", "r", rated_at="2026-10-16T10:00:00Z") # submitted counts as yes: unsure
    lq.set_human("c", "submitted", "David Wood", at="2026-10-18T10:00:00Z")
    lq.add_judgment("d", "claude", "m", "yes", "r", rated_at="2026-10-16T10:00:00Z")   # undecided: ignored
    records = {r["judge"]: (r["decided"], r["matches"], r["misses"], r["false_alarms"]) for r in lq.judge_records()}
    assert records == {"claude": (3, 1, 0, 1), "grok": (1, 0, 1, 0)}
