"""Start the draft suggests what to include (David, 7 Nov 2026): Claude, the Writer's model, reads the call, Velocity's
facts, the Proposal Register and the library's list, and recommends the format, how to approve, a direction and the past
work to build on. Asked from the dialog, answered by run.py --assistant, kept for the next time the dialog opens."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import run
from drafting import llm, suggest
from ledger import queries as lq
from tests.test_briefs import seed

DASHBOARD_PROPOSALS = Path(__file__).resolve().parent.parent / "dashboard" / "lib" / "proposals.ts"


def library() -> None:
    lq.save_drive_items([
        {"id": "fold-argus", "name": "2026-09-01_sam-gov_project-argus", "mime": "application/vnd.google-apps.folder",
         "path": "02 Submissions/2026-09-01_sam-gov_project-argus", "indexed_at": "2026-11-07T12:00:00Z"},
        {"id": "fold-scribe", "name": "2026-09-25_vulcan-sof_ai-digital-scribe", "mime": "application/vnd.google-apps.folder",
         "path": "02 Submissions/2026-09-25_vulcan-sof_ai-digital-scribe", "indexed_at": "2026-11-07T12:00:00Z"},
        {"id": "file-cap", "name": "Capability statement.pdf", "mime": "application/pdf",
         "path": "01 Company Reference/Capability statement.pdf", "indexed_at": "2026-11-07T12:00:00Z"},
        {"id": "file-elsewhere", "name": "notes.txt", "mime": "text/plain", "path": "03 Other/notes.txt",
         "indexed_at": "2026-11-07T12:00:00Z"},
    ])
    lq.upsert_proposal({"submission_id": "2026-09-01_sam-gov_project-argus", "title": "Project Argus", "agency": "DOD",
                        "outcome": "pending", "why_won_or_lost": "", "themes": "legacy modernization"})


ANSWER = {"format": "White paper", "format_why": "The call asks for white papers.", "approval_mode": "key_gates",
          "approval_why": "Familiar ground: Project Argus was the same kind of bid.",
          "direction": "Lead with the legacy modernization work in PP-01 — and Echo (PR-01).",
          "builds_on": [{"id": "fold-argus", "why": "The closest past bid."}, {"id": "made-up", "why": "x"},
                        {"id": "file-cap", "why": "The capability statement."}]}


def fenced(value: Any) -> str:
    return "Here it is.\n```json\n" + json.dumps(value) + "\n```"


def test_the_formats_match_the_dashboard_s_list() -> None:
    text = DASHBOARD_PROPOSALS.read_text(encoding="utf-8")
    listed = text.split("export const FORMATS = [", 1)[1].split("]", 1)[0]
    assert [f.strip().strip('"') for f in listed.split(",")] == list(suggest.FORMATS)


def test_the_prompt_holds_the_call_the_ranked_register_and_the_library_s_ids(ledger_db: str) -> None:
    seed("samgov-argus", "SAM.gov", "yes", 6.5)
    library()
    prompt = suggest.build_prompt(lq.get_call("samgov-argus"))
    for words in ("samgov-argus", "Project Argus", "fold-argus", "2026-09-01_sam-gov_project-argus", "fold-scribe",
                  "file-cap", "Capability statement.pdf"):
        assert words in prompt.user, words
    assert "file-elsewhere" not in prompt.user   # only submissions and company reference files can be built on
    assert "White paper" in prompt.system and "key_gates" in prompt.system and "NEEDS FACT" in prompt.system


def test_an_answer_is_checked_before_it_is_kept(ledger_db: str) -> None:
    kept = suggest.parse(fenced(ANSWER), {"fold-argus", "fold-scribe", "file-cap"})
    assert kept["format"] == "White paper" and kept["approval_mode"] == "key_gates"
    assert [b["id"] for b in kept["builds_on"]] == ["fold-argus", "file-cap"]   # an id not on the list is dropped
    assert "—" not in kept["direction"] and "PP-01" in kept["direction"]
    odd = suggest.parse(fenced({**ANSWER, "format": "Poem", "approval_mode": "sometimes", "builds_on": "nope"}), set())
    assert (odd["format"], odd["approval_mode"], odd["builds_on"]) == (None, None, [])
    with pytest.raises(suggest.SuggestionError):
        suggest.parse("no json here", set())


def test_claude_is_asked_with_the_facts_first_and_the_cost_comes_back(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    seed("samgov-argus", "SAM.gov", "yes", 6.5)
    library()
    seen: dict[str, Any] = {}

    def fake_generate(prompt: str, system: str = "", model: str | None = None, max_tokens: int = 0, timeout: float = 0,
                      phase_label: str = "", *, on_usage: Any = None, prefix: str = "", **_: Any) -> str:
        seen.update(prompt=prompt, system=system, model=model, prefix=prefix)
        on_usage(llm.Usage("draft suggestion", "claude-sonnet-5-5", 1000, 500, 20000, 0, 3.0, False, "r"))
        return fenced(ANSWER)

    monkeypatch.setattr(suggest, "generate", fake_generate)
    kept, cost = suggest.suggest("samgov-argus")
    assert seen["model"] == llm.writer_model() and seen["prefix"].startswith("VELOCITY FACTS")
    assert kept["builds_on"][0]["id"] == "fold-argus"
    assert cost == pytest.approx((1000 * 2 + 500 * 10 + 20000 * 0.1) / 1_000_000)


def test_one_suggestion_waits_per_call_and_the_newest_answer_is_kept(ledger_db: str) -> None:
    first = lq.ask_suggestion("samgov-argus", "David Wood")
    assert lq.ask_suggestion("samgov-argus", "Shaun Jones") == first   # already waiting: the same request
    taken = lq.claim_next_suggestion()
    assert taken and taken["id"] == first and lq.claim_next_suggestion() is None
    lq.finish_suggestion(first, "done", {"format": "White paper"}, model="claude-sonnet-5-5", cost_usd=0.1)
    newest = lq.latest_suggestion("samgov-argus")
    assert newest["state"] == "done" and json.loads(newest["suggestion"]) == {"format": "White paper"}
    assert lq.assistant_spend_today() == pytest.approx(0.1)


def test_the_assistant_answers_a_waiting_suggestion(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    seed("samgov-argus", "SAM.gov", "yes", 6.5)
    library()
    monkeypatch.setattr(run, "draft_suggestion", lambda call_id: ({**ANSWER, "builds_on": [ANSWER["builds_on"][0]]}, 0.05))
    asked = lq.ask_suggestion("samgov-argus", "David Wood")
    assert run.run_assistant(model=object(), max_questions=1, poll_s=0) == 0
    row = lq.get_suggestion(asked)
    assert row["state"] == "done" and row["cost_usd"] == pytest.approx(0.05) and row["model"] == llm.writer_model()
    assert json.loads(row["suggestion"])["format"] == "White paper"


def test_a_failed_suggestion_says_why(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(call_id: str) -> tuple[dict[str, Any], float]:
        raise suggest.SuggestionError("Claude's answer held no suggestion")

    monkeypatch.setattr(run, "draft_suggestion", broken)
    asked = lq.ask_suggestion("samgov-argus", "David Wood")
    assert run.run_assistant(model=object(), max_questions=1, poll_s=0) == 0
    row = lq.get_suggestion(asked)
    assert row["state"] == "failed" and "Try again" in row["note"]
