"""The assistant's command line and its scheduled Slack jobs."""
from __future__ import annotations

import json

import pytest

from assistant import __main__ as cli
from ledger import queries as lq
from tests.test_assistant_tools import NOW, add_call, due, portal  # noqa: F401  (fixture reused)


@pytest.fixture
def posts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    sent: list[str] = []
    monkeypatch.setattr(cli, "post_text", lambda text: sent.append(text) or "1.0")
    return sent


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


def test_remind_posts_only_when_something_is_due(ledger_db: str, portal, posts, capsys) -> None:
    assert cli.main(["remind"]) == 0
    assert posts == [] and "nothing to post" in capsys.readouterr().out
    run = lq.start_run("Example")
    add_call("ex-soon", "Soon", run, due_date=due(3.5))
    lq.set_human("ex-soon", "pursue", "David Wood")
    assert cli.main(["remind"]) == 0
    assert len(posts) == 1 and posts[0].startswith("*Deadline reminder*") and "Soon" in posts[0]


def test_post_summary_covers_each_portal_and_the_scraper(ledger_db: str, portal, posts) -> None:
    run = lq.start_run("Example", component="example")
    add_call("ex-1", "Analytics software", run)
    lq.finish_run(run, "completed", {"fetched": 1})
    assert cli.main(["post-summary"]) == 0
    assert len(posts) == 1
    assert "*Example, last 7 days*" in posts[0] and "Scraper:" in posts[0]
