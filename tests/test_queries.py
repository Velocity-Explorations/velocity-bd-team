from __future__ import annotations

import csv
import json
from pathlib import Path

from ledger import queries as lq


def _call(call_id: str, **overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "id": call_id,
        "portal": "vulcan_sof",
        "title": f"Title for {call_id}",
        "type": "RFI",
        "department": "USSOCOM",
        "naics_code": "541511",
        "set_aside": None,
        "posted_date": "2026-10-01",
        "due_date": "2026-11-01",
        "description": "Some text",
        "url": f"https://example.invalid/{call_id}",
        "source_type": "scrape",
        "extra": {"vulcan_collection": call_id},
    }
    base.update(overrides)
    return base


# ----------------------------------------------------------------------------- runs

def test_start_and_finish_run(ledger_db: str) -> None:
    run_id = lq.start_run("vulcan_sof", dry_run=True)
    row = lq.get_run(run_id)
    assert row is not None
    assert row["status"] == "running" and row["dry_run"] == 1 and row["component"] == "vulcan_sof"
    lq.finish_run(run_id, "completed", {"fetched": 3, "filtered": 2, "reviewed": 2, "new": 1}, log_path=Path("data/x.log"))
    row = lq.get_run(run_id)
    assert row is not None
    assert row["status"] == "completed"
    assert json.loads(row["stage_counts"])["fetched"] == 3
    assert row["finished_at"] and row["finished_at"].endswith("Z")


# ---------------------------------------------------------------------------- calls

def test_upsert_call_new_then_update_keeps_human_notes(ledger_db: str) -> None:
    run1 = lq.start_run("vulcan_sof")
    assert lq.upsert_call(_call("vulcan-a"), run1) is True

    lq.append_note("vulcan-a", "looks promising", by="david", at="2026-10-15T10:00:00Z")
    lq.set_human("vulcan-a", "pursue", by="david", at="2026-10-15T10:01:00Z")
    lq.set_review("vulcan-a", "yes", "fits")

    run2 = lq.start_run("vulcan_sof")
    assert lq.upsert_call(_call("vulcan-a", title="Updated title"), run2) is False

    row = lq.get_call("vulcan-a")
    assert row is not None
    assert row["title"] == "Updated title"
    assert row["human_notes"] == "[2026-10-15T10:00:00Z david] looks promising"
    assert row["human_status"] == "pursue"
    assert row["ai_verdict"] == "yes"
    assert row["first_run_id"] == run1 and row["last_run_id"] == run2
    assert json.loads(row["extra"]) == {"vulcan_collection": "vulcan-a"}


def test_set_human_and_append_note_round_trip(ledger_db: str) -> None:
    run_id = lq.start_run("vulcan_sof")
    lq.upsert_call(_call("vulcan-b"), run_id)
    lq.set_human("vulcan-b", "submitted", by="aisha", at="2026-10-15T12:00:00Z")
    lq.append_note("vulcan-b", "first", by="aisha", at="2026-10-15T12:01:00Z")
    notes = lq.append_note("vulcan-b", "second", by="david", at="2026-10-15T12:02:00Z")
    row = lq.get_call("vulcan-b")
    assert row is not None
    assert (row["human_status"], row["human_by"], row["human_at"]) == ("submitted", "aisha", "2026-10-15T12:00:00Z")
    assert row["human_notes"] == notes
    assert notes.splitlines() == [
        "[2026-10-15T12:01:00Z aisha] first",
        "[2026-10-15T12:02:00Z david] second",
    ]


def test_new_calls_only_returns_calls_first_seen_in_run(ledger_db: str) -> None:
    run1 = lq.start_run("vulcan_sof")
    lq.upsert_call(_call("vulcan-old"), run1)
    lq.set_review("vulcan-old", "yes", "r")

    run2 = lq.start_run("vulcan_sof")
    lq.upsert_call(_call("vulcan-old"), run2)       # seen again
    lq.upsert_call(_call("vulcan-new-yes"), run2)
    lq.upsert_call(_call("vulcan-new-maybe"), run2)
    lq.upsert_call(_call("vulcan-new-no"), run2)
    lq.upsert_call(_call("vulcan-new-unreviewed"), run2)
    lq.set_review("vulcan-new-yes", "yes", "r")
    lq.set_review("vulcan-new-maybe", "maybe", "r")
    lq.set_review("vulcan-new-no", "no", "r")

    ids = sorted(r["id"] for r in lq.new_calls(run2))
    assert ids == ["vulcan-new-maybe", "vulcan-new-yes"]
    assert [r["id"] for r in lq.new_calls(run1)] == ["vulcan-old"]


def test_recent_decisions_orders_newest_first(ledger_db: str) -> None:
    run_id = lq.start_run("vulcan_sof")
    for n in range(4):
        lq.upsert_call(_call(f"vulcan-{n}"), run_id)
    lq.set_human("vulcan-0", "pursue", "d", at="2026-10-10T00:00:00Z")
    lq.set_human("vulcan-1", "dismissed", "d", at="2026-10-12T00:00:00Z")
    lq.set_human("vulcan-2", "not_relevant", "d", at="2026-10-11T00:00:00Z")
    # vulcan-3 has no decision
    decided = lq.recent_decisions()
    assert [r["id"] for r in decided] == ["vulcan-1", "vulcan-2", "vulcan-0"]
    assert [r["id"] for r in lq.recent_decisions(limit=2)] == ["vulcan-1", "vulcan-2"]


def test_calls_for_review_and_pending_feedback(ledger_db: str) -> None:
    run_id = lq.start_run("vulcan_sof")
    for n in ("k1", "k2", "rej", "done"):
        lq.upsert_call(_call(f"vulcan-{n}"), run_id)
    lq.set_filter("vulcan-k1", "kept", tier="broad", keywords=["autonomy"])
    lq.set_filter("vulcan-k2", "kept")
    lq.set_filter("vulcan-rej", "rejected", reason="excluded NAICS")
    lq.set_filter("vulcan-done", "kept")
    lq.set_review("vulcan-done", "no", "not us")
    assert sorted(r["id"] for r in lq.calls_for_review(run_id)) == ["vulcan-k1", "vulcan-k2"]
    k1 = lq.get_call("vulcan-k1")
    assert k1 is not None and json.loads(k1["matched_keywords"]) == ["autonomy"]

    lq.set_slack("vulcan-k1", "C123", "1700000000.000100")
    lq.set_slack("vulcan-k2", "C123", "1700000000.000200")
    lq.set_human("vulcan-k2", "pursue", "d")
    assert [r["id"] for r in lq.pending_feedback()] == ["vulcan-k1"]
    k1 = lq.get_call("vulcan-k1")
    assert k1 is not None and k1["posted_at"] is not None and k1["slack_ts"] == "1700000000.000100"


def test_export_csv(ledger_db: str, tmp_path: Path) -> None:
    run_id = lq.start_run("vulcan_sof")
    lq.upsert_call(_call("vulcan-x"), run_id)
    lq.upsert_call(_call("vulcan-y"), run_id)
    out = tmp_path / "exports" / "calls.csv"
    assert lq.export_csv(out) == 2
    with out.open(encoding="utf-8", newline="") as fh:
        data = list(csv.DictReader(fh))
    assert [d["id"] for d in data] == ["vulcan-x", "vulcan-y"]
    assert "human_status" in data[0]


# ------------------------------------------------------------------------ proposals

def test_upsert_and_list_proposals(ledger_db: str) -> None:
    assert lq.upsert_proposal({
        "submission_id": "2025-03-01_sbir_edge-ai",
        "title": "Edge AI",
        "portal": "sbir",
        "outcome": "won",
        "submitted_date": "2025-03-01",
        "strength_rating": 4,
        "themes": ["edge", "autonomy"],
    }) is True
    assert lq.upsert_proposal({
        "submission_id": "2025-06-01_vulcan_sof_sensor",
        "title": "Sensor",
        "portal": "vulcan_sof",
        "outcome": "lost",
        "submitted_date": "2025-06-01",
    }) is True
    assert lq.upsert_proposal({"submission_id": "2025-06-01_vulcan_sof_sensor", "outcome": "shortlisted"}) is False

    assert len(lq.list_proposals()) == 2
    assert [p["submission_id"] for p in lq.list_proposals(portal="sbir")] == ["2025-03-01_sbir_edge-ai"]
    assert [p["outcome"] for p in lq.list_proposals(portal="vulcan_sof")] == ["shortlisted"]
    assert lq.list_proposals(outcome="won")[0]["title"] == "Edge AI"
    assert json.loads(lq.list_proposals(outcome="won")[0]["themes"]) == ["edge", "autonomy"]


# ------------------------------------------------------------------ change requests

def test_a_request_moves_from_proposed_to_applied(ledger_db: str) -> None:
    rid = lq.create_request("scan", "Scan Vulcan SOF now", "Dana", portal="vulcan_sof", reason="new calls",
                            payload={}, preview={"text": "The last scan finished yesterday."})
    req = lq.get_request(rid)
    assert req and req["status"] == "proposed" and req["kind"] == "scan" and req["portal"] == "vulcan_sof"
    assert req["requested_by"] == "Dana" and req["reason"] == "new calls" and req["requested_at"]
    assert json.loads(req["preview"])["text"] == "The last scan finished yesterday."
    assert lq.claim_request(rid) is False                      # only approved requests can be claimed
    assert lq.decide_request(rid, True, "David Wood", note="go ahead") is True
    assert lq.decide_request(rid, False, "Someone else") is False   # decided once, never twice
    req = lq.get_request(rid)
    assert req["status"] == "approved" and req["decided_by"] == "David Wood" and req["decision_note"] == "go ahead"
    assert lq.claim_request(rid) is True and lq.claim_request(rid) is False
    assert lq.finish_request(rid, "applied", "Run 7 completed.") is True
    req = lq.get_request(rid)
    assert req["status"] == "applied" and req["result"] == "Run 7 completed." and req["applied_at"]


def test_a_rejected_request_is_never_applied(ledger_db: str) -> None:
    rid = lq.create_request("scan", "Scan now", "assistant", portal="vulcan_sof")
    assert lq.decide_request(rid, False, "David Wood") is True
    assert lq.get_request(rid)["status"] == "rejected"
    assert lq.claim_request(rid) is False


def test_a_claimed_request_can_go_back_to_waiting(ledger_db: str) -> None:
    rid = lq.create_request("keyword_change", "Add a keyword", "assistant", portal="vulcan_sof")
    lq.decide_request(rid, True, "David Wood")
    assert lq.note_request(rid, "Waiting: the checkout is on branch dev.") is True
    assert lq.get_request(rid)["result"] == "Waiting: the checkout is on branch dev."
    assert lq.claim_request(rid) is True
    assert lq.release_request(rid, "Waiting: another pipeline run is in progress.") is True
    req = lq.get_request(rid)
    assert req["status"] == "approved" and req["result"].startswith("Waiting: another pipeline")
    assert lq.finish_request(rid, "applied", "x") is False     # not claimed any more


def test_finish_request_only_accepts_an_outcome(ledger_db: str) -> None:
    rid = lq.create_request("scan", "Scan now", "assistant", portal="vulcan_sof")
    try:
        lq.finish_request(rid, "approved", "no")
    except ValueError as exc:
        assert "applied" in str(exc)
    else:
        raise AssertionError("finish_request accepted a status that is not an outcome")


def test_list_and_find_open_requests(ledger_db: str) -> None:
    first = lq.create_request("scan", "Scan Vulcan", "assistant", portal="vulcan_sof", payload={})
    second = lq.create_request("rereview", "Re-review a call", "assistant", call_id="vulcan-1",
                               payload={"context": "C2 software"})
    third = lq.create_request("scan", "Scan Vulcan again", "assistant", portal="vulcan_sof", payload={})
    lq.decide_request(third, False, "David Wood")
    assert [r["id"] for r in lq.list_requests()] == [third, second, first]          # newest first
    assert [r["id"] for r in lq.list_requests("proposed", oldest_first=True)] == [first, second]
    assert [r["id"] for r in lq.list_requests(("rejected", "applied"))] == [third]
    assert lq.find_open_request("scan", "vulcan_sof", None, {})["id"] == first
    assert lq.find_open_request("rereview", None, "vulcan-1", {"context": "C2 software"})["id"] == second
    assert lq.find_open_request("rereview", None, "vulcan-1", {"context": "other"}) is None
    assert lq.count_requests("proposed") == 2
