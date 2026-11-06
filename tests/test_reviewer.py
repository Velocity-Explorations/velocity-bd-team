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
    assert "weight that positively.\n\nTags: choose only from this list." in p   # the tag list comes last (PRO-556)
    with_blocks = reviewer.build_prompt(ROW, "PAST\n", "FEEDBACK\n")
    assert "PAST\nFEEDBACK\n" in with_blocks


def test_the_prompt_asks_for_the_main_work_and_to_rate_the_call_on_it() -> None:
    p = reviewer.build_prompt(ROW)
    assert "MAIN WORK: [the one Work tag" in p and "Rate the call on its main work." in p
    assert p.index("TAGS: [") < p.index("MAIN WORK: [") < p.index("SUMMARY: [")


def test_the_profile_says_what_the_record_shows() -> None:
    profile = reviewer.COMPANY_CONTEXT
    assert "launch, range and space operations" in profile and "AI decision support for command and control" in profile
    assert "building the vehicles, drones, weapons or control systems themselves" in profile
    assert "autonomous systems software" not in profile and "creating C2 tools" not in profile
    assert not any(chr(c) in profile for c in (0x2013, 0x2014))


def test_each_judge_names_the_main_work_on_its_newest_judgment(ledger_db: str) -> None:
    run_id = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": "vulcan-1", "portal": "Vulcan SOF", "title": "AI thing", "description": "d"}, run_id)
    lq.set_filter("vulcan-1", "kept", tier="broad")
    rows = lq.calls_for_review(run_id)
    reviewer.review_calls(rows, FakeModel(["VERDICT: yes\nREASON: fits\nTAGS: Software, Cyber\nMAIN WORK: software."]), sleep=lambda _s: None)
    reviewer.judge_calls(rows, FakeModel(["VERDICT: no\nREASON: no\nMAIN WORK: Services"]), "grok", sleep=lambda _s: None)
    assert lq.main_work_by_call() == {"vulcan-1": {"claude": "Software", "grok": "Services"}}
    reviewer.judge_calls(rows, FakeModel(["VERDICT: no\nREASON: no\nMAIN WORK: USSF"]), "grok", sleep=lambda _s: None)
    assert lq.main_work_by_call() == {"vulcan-1": {"claude": "Software"}}   # a customer is no main work, and the new answer stands


def test_a_failure_to_store_the_main_work_never_stops_a_review(ledger_db: str, monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = lq.start_run("Vulcan SOF")
    lq.upsert_call({"id": "vulcan-1", "portal": "Vulcan SOF", "title": "AI thing", "description": "d"}, run_id)
    lq.set_filter("vulcan-1", "kept", tier="broad")

    def broken(*_args: object) -> None:
        raise RuntimeError("no such column")

    monkeypatch.setattr(reviewer, "set_main_work", broken)
    passed, _ = reviewer.review_calls(lq.calls_for_review(run_id), FakeModel(["VERDICT: yes\nREASON: fits\nMAIN WORK: Software"]), sleep=lambda _s: None)
    assert [r.verdict for r in passed] == ["yes"] and lq.get_call("vulcan-1")["ai_verdict"] == "yes"


def test_events_are_judged_on_topic_and_other_calls_are_unchanged() -> None:
    event = reviewer.build_prompt({"title": "Space Industry Days 2026", "type": "Industry day", "portal": "SSC Front Door"})
    call = reviewer.build_prompt({"title": "Edge AI", "type": "OTA Prototype", "portal": "Vulcan SOF"})
    assert reviewer.EVENT_GUIDANCE in event and reviewer.EVENT_GUIDANCE not in call
    assert all(reviewer.EVENT_GUIDANCE in reviewer.build_prompt({"type": t}) for t in reviewer.EVENT_TYPES)


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


class FakeAnthropic:
    """Stands in for the Anthropic SDK's client: keeps each request and answers with the next scripted response."""

    def __init__(self, responses: list[object]) -> None:
        self.responses = list(responses)
        self.requests: list[dict] = []
        self.messages = self

    def with_options(self, **kwargs: object) -> FakeAnthropic:
        return self

    def create(self, **kwargs: object) -> object:
        self.requests.append(kwargs)
        return self.responses.pop(0)


def answer(stop_reason: str, *blocks: tuple[str, str]) -> object:
    from types import SimpleNamespace

    return SimpleNamespace(stop_reason=stop_reason, content=[SimpleNamespace(type=kind, text=text) for kind, text in blocks])


def claude(*responses: object) -> reviewer.AnthropicModel:
    model = object.__new__(reviewer.AnthropicModel)
    model.model, model._client = reviewer.MODEL_ID, FakeAnthropic(list(responses))
    return model


def test_the_review_has_room_to_think_and_still_answer() -> None:
    # 4 Nov: at 1,024 tokens, 4 of 262 SAM.gov reviews spent them all thinking and 24 more were cut mid-reason.
    model = claude(answer("end_turn", ("thinking", ""), ("text", "VERDICT: yes\nREASON: Fits.")))
    assert model.complete("p", timeout=5) == "VERDICT: yes\nREASON: Fits."
    assert model._client.requests[0]["max_tokens"] >= 4096


def test_an_answer_cut_off_at_the_token_limit_is_a_failed_try_never_a_review() -> None:
    cut = answer("max_tokens", ("thinking", ""), ("text", "VERDICT: no\nREASON: The work is hardw"))
    with pytest.raises(RuntimeError, match="token limit"):
        claude(cut).complete("p", timeout=5)
    verdict, reason = reviewer.ask_model("p", claude(answer("max_tokens", ("thinking", "")), cut), sleep=lambda s: None)
    assert verdict == "maybe" and reason.startswith("Review error: RuntimeError: answer cut off at the token limit")
    assert reviewer.ask_model("p", claude(cut, answer("end_turn", ("text", "VERDICT: no\nREASON: Hardware."))),
                              sleep=lambda s: None) == ("no", "Hardware.")


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
