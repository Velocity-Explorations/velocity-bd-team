"""Each call the team pursues gets an issue in Linear's Pursuits project, kept in step with the call (David, 4 Nov
2026): opened on Pursue, In Progress when drafting starts, Done when the call is marked Submitted, a comment for its
result, Canceled with the reason when the Pursue is withdrawn. The sync acts only when the call's stage moves on."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from ledger import queries as lq
from ledger.db import q, tx
from linear import pursuits
from linear.board import LinearBoard

NOW = datetime(2026, 11, 4, 19, 0, tzinfo=timezone.utc)
DASHES = (chr(0x2013), chr(0x2014))


class FakeBoard:
    """Stands in for Linear: records what the sync opens, moves and comments on."""

    def __init__(self) -> None:
        self.opened: list[dict[str, Any]] = []
        self.moves: list[tuple[str, str]] = []
        self.comments: list[tuple[str, str]] = []

    def open(self, title: str, body: str, due: str | None, priority: int, assignee_email: str | None) -> dict[str, str]:
        n = len(self.opened) + 1
        issue = {"id": f"uuid-{n}", "identifier": f"OPS-{100 + n}", "url": f"https://linear.example.invalid/issue/OPS-{100 + n}"}
        self.opened.append({"title": title, "body": body, "due": due, "priority": priority, "assignee": assignee_email, **issue})
        return issue

    def move(self, issue_id: str, state: str) -> bool:
        self.moves.append((issue_id, state))
        return True

    def comment(self, issue_id: str, body: str) -> bool:
        self.comments.append((issue_id, body))
        return True


@pytest.fixture
def team(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> FakeBoard:
    monkeypatch.setenv("DASHBOARD_USERS", "David Wood <david@velocity.example.invalid>=U0123456, Shaun")
    monkeypatch.setenv("DASHBOARD_URL", "https://bd.example.invalid/")
    return FakeBoard()


def a_call(call_id: str, title: str = "CBM+ Software and Analytics Development", due: str = "2026-11-13T15:00:00-05:00") -> None:
    run_id = lq.start_run("SAM.gov")
    lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": title, "url": f"https://sam.example.invalid/{call_id}",
                    "type": "Sources Sought", "department": "DEPT OF THE NAVY", "set_aside": "Total Small Business",
                    "naics_code": "541715", "due_date": due,
                    "extra": {"samgov_solicitation_number": "N00024-27-R-0001",
                              "samgov_contacts": [{"name": "Pat Lee", "email": "pat.lee@navy.example.invalid"}]}}, run_id)
    with tx() as conn:
        q(conn, "UPDATE calls SET filter_result = 'kept', ai_verdict = 'yes', ai_reasoning = ?, ai_summary = ? WHERE id = ?",
          ("Predictive maintenance software and AI analytics match Velocity's data work.",
           "The Navy wants software and analytics for condition-based maintenance; responses are due 13 Nov.", call_id))
    lq.add_judgment(call_id, "grok", "grok-4.7", "maybe", "Software fits, but the scope is broad.")


def stage(call_id: str) -> str | None:
    with tx() as conn:
        row = q(conn, "SELECT stage FROM linear_issues WHERE call_id = ?", (call_id,)).fetchone()
    return row[0] if row else None


def test_a_call_marked_pursue_gets_one_issue(team: FakeBoard) -> None:
    a_call("c1")
    lq.set_human("c1", "pursue", "David Wood")
    changes = pursuits.sync(team, now=NOW)
    assert len(team.opened) == 1 and changes == ["c1: opened OPS-101"]
    issue = team.opened[0]
    assert issue["title"] == "Submit CBM+ Software and Analytics Development by 13 Nov"
    assert issue["due"] == "2026-11-13" and issue["priority"] == 2   # due in 9 days: High
    assert issue["assignee"] == "david@velocity.example.invalid"
    body = issue["body"]
    assert body.startswith("Marked Pursue on the dashboard by David Wood on ")
    assert "The Navy wants software and analytics" in body
    assert "Claude, yes: Predictive maintenance" in body and "Grok, maybe: Software fits" in body
    assert "Set-aside: Total Small Business" in body and "NAICS: 541715" in body and "Solicitation: N00024-27-R-0001" in body
    assert "Contact: Pat Lee, pat.lee@navy.example.invalid" in body
    assert "[The call on SAM.gov](https://sam.example.invalid/c1)" in body
    assert "[The call on the dashboard](https://bd.example.invalid/proposals/c1)" in body
    assert stage("c1") == "pursued"
    assert pursuits.sync(team, now=NOW) == [] and len(team.opened) == 1 and team.moves == []


def test_the_issue_moves_with_the_call(team: FakeBoard) -> None:
    a_call("c1")
    lq.set_human("c1", "pursue", "David Wood")
    pursuits.sync(team, now=NOW)
    pursuit_id = lq.start_pursuit("c1", "David Wood")
    assert pursuits.sync(team, now=NOW) == ["c1: OPS-101 moved to In Progress"]
    with tx() as conn:
        q(conn, "UPDATE pursuits SET state = 'submitted', submitted_by = 'Shaun', submitted_at = '2026-11-12', "
                "confirmation_number = 'ABC123' WHERE id = ?", (pursuit_id,))
    lq.set_human("c1", "submitted", "Shaun")
    assert pursuits.sync(team, now=NOW) == ["c1: OPS-101 moved to Done"]
    assert team.comments[-1] == ("uuid-1", "Marked Submitted on the dashboard by Shaun on 12 Nov 2026, confirmation ABC123.")
    with tx() as conn:
        q(conn, "UPDATE pursuits SET result = 'won', result_by = 'Shaun', result_at = '2026-12-01T16:00:00Z', "
                "debrief = 'Strong technical approach.' WHERE id = ?", (pursuit_id,))
    assert pursuits.sync(team, now=NOW) == ["c1: OPS-101 result recorded"]
    assert team.comments[-1] == ("uuid-1", "Result recorded by Shaun on 1 Dec 2026: Won. Debrief: Strong technical approach.")
    assert team.moves == [("uuid-1", "In Progress"), ("uuid-1", "Done")] and stage("c1") == "result"


def test_a_withdrawn_pursue_cancels_the_issue_and_pursuing_again_opens_a_new_one(team: FakeBoard) -> None:
    a_call("c1")
    lq.set_human("c1", "pursue", "David Wood")
    pursuits.sync(team, now=NOW)
    lq.set_human("c1", "not_relevant", "Shaun")
    assert pursuits.sync(team, now=NOW) == ["c1: OPS-101 canceled"]
    assert team.moves == [("uuid-1", "Canceled")]
    assert team.comments == [("uuid-1", "Pursue withdrawn on the dashboard by Shaun: the call is now Not relevant.")]
    lq.set_human("c1", "pursue", "Shaun")
    assert pursuits.sync(team, now=NOW) == ["c1: opened OPS-102"]   # a canceled issue is never reopened
    assert team.opened[-1]["assignee"] is None and stage("c1") == "pursued"   # Shaun has no address on file


def test_a_closed_draft_cancels_its_issue(team: FakeBoard) -> None:
    a_call("c1")
    lq.set_human("c1", "pursue", "David Wood")
    pursuit_id = lq.start_pursuit("c1", "David Wood")
    assert pursuits.sync(team, now=NOW) == ["c1: opened OPS-101", "c1: OPS-101 moved to In Progress"]
    lq.close_pursuit(pursuit_id, "David Wood", "agency extended the deadline into next year")
    assert pursuits.sync(team, now=NOW) == ["c1: OPS-101 canceled"]
    assert team.comments[-1] == ("uuid-1", "The draft was closed on the dashboard: the call is no longer pursued.")


def test_a_call_submitted_before_the_sync_gets_no_issue(team: FakeBoard) -> None:
    a_call("c2")
    lq.set_human("c2", "submitted", "Shaun")
    assert pursuits.sync(team, now=NOW) == [] and team.opened == []


def test_a_call_whose_deadline_has_passed_gets_no_issue(team: FakeBoard) -> None:
    # On 4 Nov the live ledger's only pursued calls had closed in August and September.
    a_call("c4", due="13 AUG 2026 : 21:59 MDT")
    lq.set_human("c4", "pursue", "David Wood")
    assert pursuits.sync(team, now=NOW) == [] and team.opened == []


def test_titles_fit_and_no_text_carries_a_dash(team: FakeBoard) -> None:
    long_title = f"NATO Request for Information: Enhanced AirC2 {DASHES[0]} System Integration and Applications Marketplace for Allies"
    a_call("c3", title=long_title, due="27 NOV 2026 : 21:59 MDT")
    lq.set_human("c3", "pursue", "David Wood")
    pursuits.sync(team, now=NOW)
    issue = team.opened[0]
    assert len(issue["title"]) <= 80 and issue["title"].endswith("by 27 Nov") and issue["title"].startswith("Submit NATO Request")
    assert not any(d in issue["title"] + issue["body"] for d in DASHES)
    assert issue["due"] == "2026-11-27" and issue["priority"] == 3   # 23 days out: Medium


def test_a_deadline_without_a_time_zone_says_so_and_spacing_is_tidied(team: FakeBoard) -> None:
    # OPS-97 (5 Nov): SAM.gov gave "2026-11-13T17:00:00" with no zone, and the issue showed it as 10:00 MST.
    a_call("c5", due="2026-11-13T17:00:00")
    with tx() as conn:
        q(conn, "UPDATE calls SET department = ? WHERE id = ?", ("DEPT OF DEFENSE / DEFENSE ADVANCED RESEARCH PROJECTS AGENCY  (DARPA)", "c5"))
    lq.set_human("c5", "pursue", "David Wood")
    pursuits.sync(team, now=NOW)
    body = team.opened[0]["body"]
    assert "- Deadline: 13 Nov 2026 17:00 (no time zone given)" in body
    assert "- Agency: DEPT OF DEFENSE / DEFENSE ADVANCED RESEARCH PROJECTS AGENCY (DARPA)" in body
    assert team.opened[0]["due"] == "2026-11-13"


def test_priority_follows_the_deadline() -> None:
    assert pursuits.priority_for(NOW + timedelta(days=3), NOW) == 1
    assert pursuits.priority_for(NOW + timedelta(days=10), NOW) == 2
    assert pursuits.priority_for(NOW + timedelta(days=30), NOW) == 3
    assert pursuits.priority_for(None, NOW) == 3


def test_without_a_key_the_sync_says_so_and_does_nothing(ledger_db: str, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    import run

    monkeypatch.setenv("BD_LINEAR_API_KEY", "")
    assert run.main(["--linear-sync"]) == 0
    assert "BD_LINEAR_API_KEY is not set" in capsys.readouterr().out


class FakeClient:
    """Answers the board's GraphQL by operation name, and keeps what was asked."""

    def __init__(self) -> None:
        self.asked: list[tuple[str, dict[str, Any]]] = []

    def query(self, query: str, variables: dict[str, Any] | None = None) -> dict[str, Any] | None:
        name = query.split("(")[0].split()[-1]
        self.asked.append((name, variables or {}))
        answers = {
            "Team": {"teams": {"nodes": [{"id": "team-ops", "states": {"nodes": [
                {"id": "st-backlog", "name": "Backlog"}, {"id": "st-progress", "name": "In Progress"},
                {"id": "st-done", "name": "Done"}, {"id": "st-canceled", "name": "Canceled"}]}}]}},
            "Project": {"projects": {"nodes": [{"id": "proj-pursuits", "teams": {"nodes": [{"key": "OPS"}]}}]}},
            "User": {"users": {"nodes": [{"id": "user-david"}]}},
            "Open": {"issueCreate": {"success": True, "issue": {"id": "uuid-9", "identifier": "OPS-9", "url": "https://linear.example.invalid/OPS-9"}}},
            "Move": {"issueUpdate": {"success": True}},
            "Comment": {"commentCreate": {"success": True}},
        }
        return answers.get(name)


def test_the_board_sends_linear_the_issue_and_looks_each_id_up_once() -> None:
    client = FakeClient()
    board = LinearBoard(client)
    issue = board.open("Submit X by 13 Nov", "Body", "2026-11-13", 2, "david@velocity.example.invalid")
    assert issue == {"id": "uuid-9", "identifier": "OPS-9", "url": "https://linear.example.invalid/OPS-9"}
    opened = dict(client.asked)["Open"]["input"]
    assert opened == {"teamId": "team-ops", "projectId": "proj-pursuits", "stateId": "st-backlog", "title": "Submit X by 13 Nov",
                      "description": "Body", "dueDate": "2026-11-13", "priority": 2, "assigneeId": "user-david"}
    assert board.move("uuid-9", "Done") and dict(client.asked)["Move"] == {"id": "uuid-9", "input": {"stateId": "st-done"}}
    assert board.comment("uuid-9", "Note") and dict(client.asked)["Comment"] == {"input": {"issueId": "uuid-9", "body": "Note"}}
    board.open("Submit Y", "Body", None, 3, None)
    assert [name for name, _ in client.asked].count("Team") == 1 and [name for name, _ in client.asked].count("Project") == 1
    assert "dueDate" not in client.asked[-1][1]["input"] and "assigneeId" not in client.asked[-1][1]["input"]
