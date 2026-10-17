from __future__ import annotations

import pytest

from ledger import queries as lq
from review import reviewer


class FakeModel:
    """Scripted responses; an Exception instance in the script is raised."""

    def __init__(self, script: list[object]) -> None:
        self.script = list(script)
        self.prompts: list[str] = []

    def complete(self, prompt: str, timeout: float) -> str:
        self.prompts.append(prompt)
        assert timeout == reviewer.CALL_TIMEOUT_S
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return str(item)


ROW = {"id": "vulcan-1", "title": "AI Digital Scribe", "portal": "Vulcan SOF", "type": "OTA Prototype",
       "naics_code": "", "department": "USSOCOM / SOF Enterprise", "description": "x" * 1700, "match_tier": "tight"}


def test_build_prompt_has_context_fields_and_truncates_description() -> None:
    p = reviewer.build_prompt(ROW)
    assert p.startswith("Velocity Explorations is a small defense technology company")
    assert "Title: AI Digital Scribe" in p and "Agency: USSOCOM / SOF Enterprise" in p
    assert "Description: " + "x" * 1500 + "\n" in p and "x" * 1501 not in p
    assert p.rstrip().endswith("weight that positively.")
    with_blocks = reviewer.build_prompt(ROW, "PAST\n", "FEEDBACK\n")
    assert "PAST\nFEEDBACK\n" in with_blocks


def test_build_prompt_adds_the_team_context_after_the_description() -> None:
    plain = reviewer.build_prompt(ROW)
    with_context = reviewer.build_prompt(ROW, extra_context="  They want a C2 software layer,\nnot hardware. ")
    assert "Context from the team" not in plain
    assert ("x" * 1500 + "\nContext from the team: They want a C2 software layer, not hardware.\n\nRespond with exactly"
            in with_context)


def test_review_calls_passes_the_team_context_to_every_prompt(ledger_db: str) -> None:
    run_id = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": "vulcan-1", "portal": "Vulcan SOF", "title": "AI Digital Scribe"}, run_id)
    model = FakeModel(["VERDICT: yes\nREASON: software after all"])
    passed, _ = reviewer.review_calls([lq.get_call("vulcan-1")], model, extra_context="It is a software call.",
                                      sleep=lambda s: None)
    assert passed[0].verdict == "yes" and "Context from the team: It is a software call." in model.prompts[0]
    assert lq.get_call("vulcan-1")["ai_verdict"] == "yes"


@pytest.mark.parametrize(
    "text, expected",
    [
        ("VERDICT: yes\nREASON: Software and AI work.", ("yes", "Software and AI work.")),
        ("  verdict: No.\n  Reason:   hardware only  ", ("no", "hardware only")),
        ("VERDICT: maybe\nREASON: unclear scope\nextra", ("maybe", "unclear scope")),
        ("VERDICT: definitely\nREASON: ...", ("maybe", reviewer.UNPARSEABLE_REASON)),
        ("I think this is relevant.", ("maybe", reviewer.UNPARSEABLE_REASON)),
        ("VERDICT: yes", ("yes", "")),
    ],
)
def test_parse_response(text: str, expected: tuple[str, str]) -> None:
    assert reviewer.parse_response(text) == expected


def test_ask_model_retries_once_then_succeeds() -> None:
    model = FakeModel([RuntimeError("boom"), "VERDICT: yes\nREASON: fine"])
    slept: list[float] = []
    assert reviewer.ask_model("p", model, sleep=slept.append) == ("yes", "fine")
    assert slept == [reviewer.RETRY_DELAY_S] and len(model.prompts) == 2


def test_ask_model_empty_then_failure_is_maybe_with_review_error() -> None:
    model = FakeModel(["   ", ConnectionError("unreachable endpoint " + "z" * 200)])
    verdict, reason = reviewer.ask_model("p", model, sleep=lambda s: None)
    assert verdict == "maybe"
    assert reason.startswith("Review error: RuntimeError: empty response")
    assert len(reason) <= len("Review error: ") + 80


def test_review_calls_writes_ledger_and_splits(ledger_db: str) -> None:
    run = lq.start_run("Vulcan SOF")
    for n, title in enumerate(["AI thing", "Hose kit", "Odd one"]):
        lq.upsert_call({"id": f"vulcan-{n}", "portal": "Vulcan SOF", "title": title, "description": "d"}, run)
        lq.set_filter(f"vulcan-{n}", "kept", tier="broad")
    model = FakeModel([
        "VERDICT: yes\nREASON: software",
        "VERDICT: no\nREASON: hardware",
        ValueError("bad key"), ValueError("bad key"),
    ])
    rows = lq.calls_for_review(run)
    sleeps: list[float] = []
    passed, dropped = reviewer.review_calls(rows, model, past_experience_fn=lambda r: "PAST\n", sleep=sleeps.append)
    assert [r.id for r in passed] == ["vulcan-0", "vulcan-2"] and [r.id for r in dropped] == ["vulcan-1"]
    assert passed[1].verdict == "maybe" and passed[1].reason.startswith("Review error: ValueError: bad key")
    assert "PAST\n" in model.prompts[0]
    assert sleeps.count(reviewer.BETWEEN_CALLS_S) == 2 and sleeps.count(reviewer.RETRY_DELAY_S) == 1
    assert lq.calls_for_review(run) == []
    row = lq.get_call("vulcan-1")
    assert row and row["ai_verdict"] == "no" and row["ai_reasoning"] == "hardware" and row["reviewed_at"]
    assert lq.latest_run_id() == run and lq.latest_run_id(portal="nope") is None
