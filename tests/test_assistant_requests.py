"""Propose tools: each records a change request for a person to approve, and changes nothing else."""
from __future__ import annotations

import json
from datetime import timedelta

import pytest

from assistant import requests as rq
from assistant import tools
from ledger import queries as lq
from portals.registry import Portal
from tests.test_assistant_tools import NOW, add_call, due, finish, portal  # noqa: F401  (fixture reused)


@pytest.fixture(autouse=True)
def link(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rq, "dashboard_link", lambda: "https://bd.example/requests")


def test_propose_keyword_change_records_the_change_and_its_preview(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-twin", "Digital twin for ships", run)
    before = portal.keywords.read_text(encoding="utf-8")
    r = rq.propose_keyword_change("example", add_broad=["Digital Twin"], reason="twins are in our lane", requested_by="Dana")
    assert portal.keywords.read_text(encoding="utf-8") == before        # nothing changes until it is approved
    req = lq.get_request(r["request_id"])
    assert req["kind"] == "keyword_change" and req["status"] == "proposed" and req["portal"] == "example"
    assert req["requested_by"] == "Dana" and req["reason"] == "twins are in our lane"
    assert json.loads(req["payload"])["changes"]["add_broad"] == ["digital twin"]
    assert req["summary"] == "Example keywords: add broad keyword 'digital twin'"
    preview = json.loads(req["preview"])
    assert [c["id"] for c in preview["newly_kept"]] == ["ex-twin"] and "would keep 1 call" in preview["text"]
    assert r["text"].startswith(f"Request #{r['request_id']} is waiting for approval")
    assert "https://bd.example/requests" in r["text"] and not r["duplicate"]
    again = rq.propose_keyword_change("example", add_broad=["digital twin"], requested_by="Lee")
    assert again["duplicate"] and again["request_id"] == r["request_id"] and "already asks for this" in again["text"]
    with pytest.raises(tools.ToolError):
        rq.propose_keyword_change("example", remove_broad=["not there"])


def test_propose_rereview_carries_the_teams_context(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-c2", "C2 data layer", run)
    lq.set_filter("ex-c2", "kept", tier="broad", keywords=["data"])
    lq.set_review("ex-c2", "no", "Looks like hardware.")
    r = rq.propose_rereview("ex-c2", context="It is a software layer over existing radios.", requested_by="Dana")
    req = lq.get_request(r["request_id"])
    assert req["kind"] == "rereview" and req["call_id"] == "ex-c2" and req["portal"] == "example"
    assert json.loads(req["payload"]) == {"context": "It is a software layer over existing radios."}
    assert req["summary"] == "Re-review 'C2 data layer' with the team's context"
    assert "The AI review said no: Looks like hardware." in json.loads(req["preview"])["text"]
    with pytest.raises(tools.ToolError, match="context"):
        rq.propose_rereview("ex-c2", context="  ")


def test_propose_rereview_refuses_a_call_the_filter_rejected(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-lawn", "Lawn care", run)
    lq.set_filter("ex-lawn", "rejected", reason="no keyword match")
    with pytest.raises(tools.ToolError, match="keyword change"):
        rq.propose_rereview("ex-lawn", context="It mentions software.")


def test_propose_scan_says_when_the_last_scan_ran(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example", component="example")
    finish(run, "completed", {"fetched": 3}, started=NOW - timedelta(days=2))
    r = rq.propose_scan("example", reason="the program office posted new calls", requested_by="Dana")
    req = lq.get_request(r["request_id"])
    assert req["kind"] == "scan" and req["summary"] == "Scan Example now" and req["portal"] == "example"
    text = json.loads(req["preview"])["text"]
    assert "The last scan completed" in text and "took 3 minutes" in text
    assert rq.propose_scan("example")["duplicate"]


def test_propose_draft_starts_from_the_brief(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-open", "Open call", run, due_date=due(10), extra={"ex_files_required": ["White paper"]})
    r = rq.propose_draft("ex-open", notes="Lead with Echo C2.", requested_by="Dana")
    req = lq.get_request(r["request_id"])
    assert req["kind"] == "draft" and req["summary"] == "Start a response draft for 'Open call'"
    assert json.loads(req["payload"]) == {"notes": "Lead with Echo C2."}
    assert "Files required: White paper." in json.loads(req["preview"])["text"]
    add_call("ex-past", "Past call", run, due_date=due(-2))
    with pytest.raises(tools.ToolError, match="passed"):
        rq.propose_draft("ex-past")
    add_call("ex-closed", "Closed call", run, due_date=due(5), extra={"ex_closed": True})
    with pytest.raises(tools.ToolError, match="closed"):
        rq.propose_draft("ex-closed")


def test_propose_fault_report_writes_an_issue_from_the_evidence(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example", component="example")
    finish(run, "error", {}, error="TimeoutError: login page did not load")
    r = rq.propose_fault_report("example", description="Logins have failed twice this week.", requested_by="Dana")
    req = lq.get_request(r["request_id"])
    payload = json.loads(req["payload"])
    assert req["kind"] == "fault_report" and req["summary"] == "Report a scraper fault in Example"
    assert payload["title"] == "Scraper fault: Example: Logins have failed twice this week."
    assert "Logins have failed twice this week." in payload["body"]
    assert "TimeoutError: login page did not load" in payload["body"] and "Reported by Dana" in payload["body"]
    assert json.loads(req["preview"])["text"] == payload["body"]
    with pytest.raises(tools.ToolError):
        rq.propose_fault_report("example", description="  ")


def test_list_change_requests_reads_the_queue(ledger_db: str, portal: Portal) -> None:
    first = rq.propose_scan("example", requested_by="Dana")["request_id"]
    listed = rq.list_change_requests()
    assert listed["requests"][0]["id"] == first
    assert f"#{first} Scan Example now: waiting for approval (asked by Dana" in listed["text"]
    lq.decide_request(first, False, "David Wood", note="not today")
    assert "rejected by David Wood: not today" in rq.list_change_requests()["text"]
    assert rq.list_change_requests(status="applied")["text"] == "No change requests with status applied."
    assert rq.get_change_request(first)["request"]["status"] == "rejected"
    with pytest.raises(tools.ToolError):
        rq.get_change_request(999)


def test_request_tools_are_registered_and_never_take_requested_by() -> None:
    by_name = {t.name: t for t in tools.all_tools()}
    for name in ("propose_keyword_change", "propose_rereview", "propose_scan", "propose_draft", "propose_fault_report"):
        assert by_name[name].permission == "propose"
        assert "requested_by" not in by_name[name].parameters["properties"]
    assert by_name["list_change_requests"].permission == "read"
    assert by_name["get_change_request"].permission == "read"
    assert tools.tool("propose_scan").run is rq.propose_scan
