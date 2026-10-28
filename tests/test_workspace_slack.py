"""Workspace notices in Slack (PW18, phase 10): a step ready and a step behind its target, each in the call's thread;
a card for a pursued call that has none; and the 08:00 digest per owner of what waits on them. Nothing posts until
WORKSPACE_SLACK is on."""
from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

import pytest

import run
from ledger import queries as lq
from slack import workspace

TODAY = date(2026, 10, 28)


class FakeSlack:
    """Answers every call as Slack would, with a new ts each time."""

    def __init__(self) -> None:
        self.posts: list[dict[str, Any]] = []

    def call(self, method: str, params: dict[str, Any], post: bool = True) -> dict[str, Any] | None:
        assert method == "chat.postMessage"
        self.posts.append(params)
        return {"ok": True, "ts": f"1761600000.{len(self.posts):06d}", "channel": params["channel"]}


@pytest.fixture(autouse=True)
def settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SLACK_CHANNEL_ID", "C0TEAM")
    monkeypatch.setenv("WORKSPACE_SLACK", "on")
    monkeypatch.setenv("DASHBOARD_USERS", "David Wood=U0DAVID01, Shaun Jones=U0SHAUN01, Lisa Hall")
    monkeypatch.setenv("DASHBOARD_URL", "https://bd.example.invalid/")
    monkeypatch.setattr(workspace, "DIGEST_FILE", tmp_path / "slack" / "workspace_digest.txt")


def pursuit(call_id: str, owner: str = "David Wood", card: bool = True, **options: Any) -> int:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": f"Edge AI {call_id}", "due_date": "2026-12-01"}, run_id)
    lq.set_human(call_id, "pursue", owner)
    if card:
        lq.set_slack(call_id, "C0TEAM", f"1761500000.{call_id}")
    return lq.start_pursuit(call_id, owner, format="White paper", **options)


def ready(pursuit_id: int, step: str) -> dict[str, Any]:
    row = lq.claim_next_step()
    assert row is not None and row["pursuit_id"] == pursuit_id and row["step"] == step, row
    assert lq.finish_step(row["id"], summary="- done", content={"document": "# x"})
    return lq.get_step(row["id"])


def test_nothing_posts_while_workspace_posts_are_off(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    ready(pursuit("sam-1"), "discovery")
    monkeypatch.delenv("WORKSPACE_SLACK")
    slack = FakeSlack()
    assert workspace.announce(slack) == {"off": True}
    assert workspace.morning(slack, TODAY) == {"off": True}
    assert slack.posts == []


def test_a_ready_step_is_announced_once_in_the_calls_thread_with_a_mention(ledger_db: str) -> None:
    pursuit_id = pursuit("sam-1")
    ready(pursuit_id, "discovery")
    slack = FakeSlack()
    assert workspace.announce(slack) == {"cards": 0, "ready": 1}
    [post] = slack.posts
    assert (post["channel"], post["thread_ts"]) == ("C0TEAM", "1761500000.sam-1")
    assert post["text"] == ("<@U0DAVID01> Step 1, Discovery is ready for you. "
                            "<https://bd.example.invalid/proposals/sam-1?step=discovery|Open the workspace>")
    assert workspace.announce(slack) == {"cards": 0, "ready": 0}   # once per step
    assert [e["kind"] for e in lq.pursuit_events(pursuit_id)].count("slack_ready") == 1


def test_a_pursued_call_without_a_card_gets_one_and_the_notice_goes_in_its_thread(ledger_db: str) -> None:
    pursuit_id = pursuit("sam-2", card=False)
    ready(pursuit_id, "discovery")
    slack = FakeSlack()
    assert workspace.announce(slack) == {"cards": 1, "ready": 1}
    card, notice = slack.posts
    assert "thread_ts" not in card and card["blocks"]
    assert lq.get_call("sam-2")["slack_ts"] == "1761600000.000001"
    assert notice["thread_ts"] == "1761600000.000001"


def test_steps_the_worker_approves_itself_are_not_announced(ledger_db: str) -> None:
    pursuit_id = pursuit("sam-3", approval_mode="key_gates")
    lq.approve_step(ready(pursuit_id, "discovery")["id"], lq.AUTO_APPROVER)
    ready(pursuit_id, "summary")   # the worker approves it on its next pass
    slack = FakeSlack()
    assert workspace.announce(slack) == {"cards": 0, "ready": 0}


def test_the_morning_posts_behind_target_once_and_a_digest_per_owner_once_a_day(ledger_db: str) -> None:
    late = pursuit("sam-4")
    lq.set_target_dates(late, {"discovery": "2026-10-20", "submit_by": "2026-11-30"})
    ready(late, "discovery")
    failed = pursuit("sam-5")
    row = lq.claim_next_step()
    lq.fail_step(row["id"], "discovery: the model refused this request")
    other = pursuit("sam-6", owner="Shaun Jones")
    row = lq.claim_next_step()
    lq.block_step(row["id"], "budget reached", cost_usd=200.0)
    unnamed = pursuit("sam-7", owner="Lisa Hall")
    ready(unnamed, "discovery")
    slack = FakeSlack()
    assert workspace.morning(slack, TODAY) == {"behind": 1, "digests": 3}
    behind, *digests = slack.posts
    assert behind["thread_ts"] == "1761500000.sam-4"
    assert behind["text"].startswith("<@U0DAVID01> Step 1, Discovery is behind its target of 2026-10-20.")
    assert all("thread_ts" not in d for d in digests)
    by_owner = {d["text"].split(" ", 1)[0]: d["text"] for d in digests}
    assert by_owner["<@U0DAVID01>"].startswith("<@U0DAVID01> 2 steps wait on you this morning:")
    assert "Edge AI sam-4: Step 1, Discovery, ready for you" in by_owner["<@U0DAVID01>"]
    assert "Edge AI sam-5: Step 1, Discovery, failed: Retry it" in by_owner["<@U0DAVID01>"]
    assert "Edge AI sam-6: Step 1, Discovery, budget reached: raise the cap" in by_owner["<@U0SHAUN01>"]
    assert by_owner["Lisa"].startswith("Lisa Hall 1 step waits on you this morning:")   # no Slack id: the name
    assert workspace.morning(slack, TODAY) == {"behind": 0, "digests": 0}           # once a day
    assert workspace.morning(slack, date(2026, 10, 29))["digests"] == 3             # the next morning again


def test_the_run_commands_call_the_jobs(monkeypatch: pytest.MonkeyPatch) -> None:
    called: list[str] = []
    monkeypatch.setattr(workspace, "announce", lambda client=None: called.append("announce") or {"cards": 0, "ready": 0})
    monkeypatch.setattr(workspace, "morning", lambda client=None, today=None: called.append("morning") or {"behind": 0, "digests": 0})
    assert run.main(["--workspace-slack"]) == 0
    assert run.main(["--workspace-morning"]) == 0
    assert called == ["announce", "morning"]
