"""An executive summary for each call (phase 9c of docs/design/redesign-plan.md): the review's SUMMARY line, kept in
calls.ai_summary, and a backfill for open, reviewed calls that have none."""
from __future__ import annotations

from typing import Any

import pytest

import run
from ledger import queries as lq
from review import reviewer
from tests.test_reviewer import FakeModel
from tests.test_tags import seed

SUMMARY = ("The Army wants offline AI decision aids for brigade staffs. A Sources Sought notice with no award yet; "
           "answers are due 1 Dec 2026.")


def reviewed(call_id: str, **fields: Any) -> None:
    seed(call_id, **fields)
    lq.set_review(call_id, "maybe", "Partly software.")


def test_the_review_prompt_asks_for_a_summary_for_an_executive() -> None:
    prompt = reviewer.build_prompt({"title": "C2 software", "portal": "SAM.gov", "description": "software"}, "", "", "")
    assert "SUMMARY:" in prompt and "executive" in prompt
    assert "SUMMARY:" in reviewer.build_summary_prompt({"title": "C2 software", "portal": "SAM.gov", "description": "software"})


def test_the_summary_line_is_read_plainly() -> None:
    assert reviewer.parse_summary(f"VERDICT: yes\nREASON: Fits.\nSUMMARY: {SUMMARY}") == SUMMARY
    assert reviewer.parse_summary("VERDICT: yes\nREASON: Fits.") is None
    assert reviewer.parse_summary("SUMMARY:   ") is None
    dashed = "SUMMARY: The Army wants C2 tools " + chr(0x2014) + " offline. Pages 3" + chr(0x2013) + "5 matter."
    assert reviewer.parse_summary(dashed) == "The Army wants C2 tools, offline. Pages 3 to 5 matter."
    assert len(reviewer.parse_summary("SUMMARY: " + "word " * 400) or "") <= reviewer.SUMMARY_CHARS


def test_the_review_keeps_the_summary_and_works_without_one(ledger_db: str) -> None:
    reviewer.review_calls([seed()], FakeModel([f"VERDICT: yes\nREASON: Builds C2 software.\nTAGS: OTA\nSUMMARY: {SUMMARY}"]),
                          sleep=lambda s: None)
    assert lq.get_call("c-1")["ai_summary"] == SUMMARY
    reviewer.review_calls([seed("c-2")], FakeModel(["VERDICT: no\nREASON: Hardware."]), sleep=lambda s: None)
    found = lq.get_call("c-2")
    assert (found["ai_verdict"], found["ai_summary"]) == ("no", None)


def test_the_backfill_summarizes_every_call_without_a_summary(ledger_db: str, monkeypatch: pytest.MonkeyPatch,
                                                             capsys: pytest.CaptureFixture[str]) -> None:
    reviewed("open-1", due_date="2099-01-15")
    reviewed("past", due_date="2020-01-15")
    lq.set_human("past", "not_relevant", "David Wood")      # decided and past its deadline: still summarized
    reviewed("done", due_date="2099-01-15")
    lq.set_summary("done", "Already summarized.")
    seed("unreviewed", due_date="2099-01-15")
    seed("rejected", kept=False, due_date="2099-01-15")     # the keyword filter's rejects show on All calls too
    model = FakeModel([f"SUMMARY: {SUMMARY}"] * 4)
    monkeypatch.setattr(run, "review_model", lambda: model)
    assert run.backfill_summaries(dry_run=True) == 0
    assert "4 calls need a summary; about $0.00 with claude-haiku-5-5" in capsys.readouterr().out
    assert lq.get_call("open-1")["ai_summary"] is None and model.prompts == []
    assert run.backfill_summaries() == 0
    assert "Summarized 4 of 4 calls." in capsys.readouterr().out
    assert [lq.get_call(c)["ai_summary"] for c in ("open-1", "past", "done", "unreviewed", "rejected")] == [
        SUMMARY, SUMMARY, "Already summarized.", SUMMARY, SUMMARY]
    assert "SUMMARY:" in model.prompts[0] and "C2 software" in model.prompts[0]
    assert run.backfill_summaries() == 0   # a second pass finds nothing left
    assert "0 calls need a summary" in capsys.readouterr().out


def test_each_scan_summarizes_the_calls_its_review_did_not(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    seed("rejected", kept=False)
    seed("other-portal", kept=False, portal="SAM.gov")
    model = FakeModel([f"SUMMARY: {SUMMARY}"])
    monkeypatch.setattr(run, "review_model", lambda: model)
    portal = type("P", (), {"name": "Vulcan SOF"})()
    assert run.run_summaries(portal, no_review=False) == 1
    assert lq.get_call("rejected")["ai_summary"] == SUMMARY
    assert lq.get_call("other-portal")["ai_summary"] is None       # another portal's scan does its own
    assert run.run_summaries(portal, no_review=True) == 0           # --no-review asks no model
