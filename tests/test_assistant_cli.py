"""The assistant's command line. Its scheduled Slack jobs run from run.py (tests/test_pipeline.py)."""
from __future__ import annotations

import json

import pytest

from assistant import __main__ as cli
from assistant import requests as rq
from ledger import queries as lq
from tests.test_assistant_tools import add_call, portal  # noqa: F401  (fixture reused)


def test_explain_prints_text_and_json(ledger_db: str, portal, capsys) -> None:
    run = lq.start_run("Example")
    add_call("ex-1", "Lawn care", run)
    lq.set_filter("ex-1", "rejected", reason="no keyword match")
    assert cli.main(["explain", "ex-1"]) == 0
    assert "Rejected by the keyword filter" in capsys.readouterr().out
    assert cli.main(["explain", "ex-1", "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["filter"]["result"] == "rejected"


def test_a_tool_error_is_a_clean_message(ledger_db: str, portal, capsys) -> None:
    assert cli.main(["explain", "missing"]) == 2
    assert "No call with id 'missing'" in capsys.readouterr().out


def test_preview_from_the_command_line(ledger_db: str, portal, capsys) -> None:
    run = lq.start_run("Example")
    add_call("ex-twin", "Digital twin for ships", run)
    assert cli.main(["preview", "example", "--add-broad", "digital twin"]) == 0
    assert "would keep 1 call" in capsys.readouterr().out


def test_tools_lists_every_tool_with_its_permission(capsys) -> None:
    assert cli.main(["tools"]) == 0
    out = capsys.readouterr().out
    assert "explain_call" in out and "read" in out


def test_propose_and_list_requests_from_the_command_line(ledger_db: str, portal, capsys,
                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(rq, "dashboard_link", lambda: "")
    run = lq.start_run("Example")
    add_call("ex-twin", "Digital twin for ships", run)
    assert cli.main(["propose", "keyword", "example", "--add-broad", "digital twin", "--reason", "twins fit",
                     "--by", "Dana"]) == 0
    assert "Request #1 is waiting for approval" in capsys.readouterr().out
    assert cli.main(["propose", "scan", "example", "--by", "Dana"]) == 0
    assert cli.main(["propose", "fault", "example", "--description", "Logins fail."]) == 0
    capsys.readouterr()
    assert cli.main(["requests"]) == 0
    out = capsys.readouterr().out
    assert "#1 Example keywords: add broad keyword 'digital twin'" in out and "#3 Report a scraper fault" in out
    assert lq.get_request(1)["requested_by"] == "Dana" and lq.get_request(3)["requested_by"] == "command line"
    assert cli.main(["requests", "--status", "applied"]) == 0
    assert "No change requests with status applied." in capsys.readouterr().out


def test_the_slack_jobs_moved_to_run_py() -> None:
    with pytest.raises(SystemExit):
        cli.main(["remind"])
