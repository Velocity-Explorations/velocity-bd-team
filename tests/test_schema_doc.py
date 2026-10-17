"""The three example queries in docs/LEDGER_SCHEMA.md must run against the real schema."""
from __future__ import annotations

import re
from pathlib import Path

from ledger import queries as lq
from ledger.db import q, rows, tx

DOC = Path(__file__).resolve().parent.parent / "docs" / "LEDGER_SCHEMA.md"


def _doc_queries() -> dict[str, str]:
    text = DOC.read_text(encoding="utf-8")
    found = re.findall(r"### (.+?)\n.*?```sql\n(.*?)```", text, flags=re.S)
    return {title.strip(): sql.strip() for title, sql in found}


def test_doc_has_three_example_queries() -> None:
    assert set(_doc_queries()) == {"New calls this week", "Triage backlog", "Win rate by portal"}


def test_doc_queries_run(ledger_db: str) -> None:
    run_id = lq.start_run("vulcan_sof")
    lq.upsert_call({"id": "vulcan-1", "portal": "vulcan_sof", "title": "A", "due_date": "2026-11-01"}, run_id)
    lq.upsert_call({"id": "vulcan-2", "portal": "vulcan_sof", "title": "B", "due_date": "2026-10-20"}, run_id)
    lq.upsert_call({"id": "vulcan-3", "portal": "vulcan_sof", "title": "C", "due_date": "2026-10-21"}, run_id)
    for call_id in ("vulcan-1", "vulcan-2"):
        lq.set_filter(call_id, "kept", tier="broad", keywords=["software"])
    lq.set_filter("vulcan-3", "rejected", reason=r"blocklist: \bturret\b")   # dropped by a later keyword change
    lq.set_review("vulcan-1", "yes", "r")
    lq.set_review("vulcan-2", "maybe", "r")
    lq.set_review("vulcan-3", "maybe", "r")
    lq.set_human("vulcan-1", "pursue", "d")
    lq.upsert_proposal({"submission_id": "2025-01-01_sbir_a", "portal": "sbir", "outcome": "won"})
    lq.upsert_proposal({"submission_id": "2025-02-01_sbir_b", "portal": "sbir", "outcome": "lost"})
    lq.upsert_proposal({"submission_id": "2025-03-01_sbir_c", "portal": "sbir", "outcome": "pending"})
    lq.upsert_proposal({"submission_id": "2025-04-01_sam_d", "portal": "sam", "outcome": "pending"})

    queries = _doc_queries()
    with tx() as conn:
        new = rows(q(conn, queries["New calls this week"], ("2000-01-01T00:00:00Z",)))
        backlog = rows(q(conn, queries["Triage backlog"]))
        win = rows(q(conn, queries["Win rate by portal"]))

    assert len(new) == 3
    assert [r["id"] for r in backlog] == ["vulcan-2"]
    by_portal = {r["portal"]: r for r in win}
    assert by_portal["sbir"]["won"] == 1 and by_portal["sbir"]["decided"] == 2
    assert float(by_portal["sbir"]["win_rate_pct"]) == 50.0
    assert by_portal["sam"]["decided"] == 0 and by_portal["sam"]["win_rate_pct"] is None
