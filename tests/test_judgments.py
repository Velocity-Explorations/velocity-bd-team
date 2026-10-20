"""Each judge's verdict on each call is kept (migration 003_judgments), and Grok judges beside Claude."""
from __future__ import annotations

import json

import pytest

from ledger import queries as lq
from review import reviewer
from tests.test_reviewer import FakeModel


def seed(call_id: str = "c-1", title: str = "C2 software") -> dict:
    run = lq.start_run("Fake")
    lq.upsert_call({"id": call_id, "portal": "Fake", "title": title, "description": "software"}, run)
    lq.set_filter(call_id, "kept", tier="broad", keywords=["software"])
    return lq.get_call(call_id)   # type: ignore[return-value]


def test_the_newest_judgment_per_judge_wins(ledger_db: str) -> None:
    seed()
    lq.add_judgment("c-1", "claude", "claude-haiku-5-5", "maybe", "unclear")
    lq.add_judgment("c-1", "grok", "grok-4.7", "no", "hardware")
    lq.add_judgment("c-1", "claude", "claude-haiku-5-5", "yes", "after the team's context")
    got = lq.latest_judgments("c-1")
    assert {judge: (j["verdict"], j["model"]) for judge, j in got.items()} == {
        "claude": ("yes", "claude-haiku-5-5"), "grok": ("no", "grok-4.7")}
    assert lq.latest_judgments("nothing-here") == {}


def test_the_review_records_claudes_judgment_but_not_its_errors(ledger_db: str) -> None:
    reviewer.review_calls([seed()], FakeModel(["VERDICT: yes\nREASON: Builds C2 software."]), sleep=lambda s: None)
    claude = lq.latest_judgments("c-1")["claude"]
    assert claude["verdict"] == "yes" and claude["model"] == reviewer.MODEL_ID and claude["reasoning"] == "Builds C2 software."

    reviewer.review_calls([seed("c-2", "Other")], FakeModel([RuntimeError("a"), RuntimeError("b")]), sleep=lambda s: None)
    assert lq.get_call("c-2")["ai_verdict"] == "maybe"   # type: ignore[index]   the fail-safe verdict still gates
    assert lq.latest_judgments("c-2") == {}               # but an error is not a judgment


def test_a_second_judge_rates_without_touching_the_gating_verdict(ledger_db: str) -> None:
    row = seed()
    lq.set_review("c-1", "maybe", "unclear")
    model = FakeModel(["VERDICT: no\nREASON: Hardware."])
    model.model = "grok-4.7"   # type: ignore[attr-defined]
    judged = reviewer.judge_calls([row], model, "grok", sleep=lambda s: None)
    assert [j.verdict for j in judged] == ["no"]
    assert lq.get_call("c-1")["ai_verdict"] == "maybe"   # type: ignore[index]
    grok = lq.latest_judgments("c-1")["grok"]
    assert (grok["verdict"], grok["model"], grok["reasoning"]) == ("no", "grok-4.7", "Hardware.")


def test_a_failed_second_judge_records_nothing(ledger_db: str) -> None:
    judged = reviewer.judge_calls([seed()], FakeModel([RuntimeError("a"), RuntimeError("b")]), "grok", sleep=lambda s: None)
    assert judged == [] and lq.latest_judgments("c-1") == {}


def test_grok_model_calls_the_responses_api(monkeypatch: pytest.MonkeyPatch) -> None:
    sent: dict = {}

    class Reply:
        def __enter__(self) -> "Reply":
            return self

        def __exit__(self, *exc: object) -> bool:
            return False

        def read(self) -> bytes:
            return json.dumps({"output": [{"type": "reasoning", "content": []},
                                          {"type": "message", "content": [{"type": "output_text", "text": "VERDICT: yes\nREASON: fits"}]}]}).encode()

    def fake_urlopen(request, timeout: float) -> Reply:
        sent.update(url=request.full_url, timeout=timeout, auth=request.get_header("Authorization"),
                    body=json.loads(request.data.decode("utf-8")))
        return Reply()

    monkeypatch.setattr(reviewer.urllib.request, "urlopen", fake_urlopen)
    model = reviewer.GrokModel(api_key="test-key")
    assert model.complete("the prompt", timeout=reviewer.CALL_TIMEOUT_S) == "VERDICT: yes\nREASON: fits"
    assert sent["url"] == "https://api.x.ai/v1/responses" and sent["auth"] == "Bearer test-key"
    assert sent["body"] == {"model": "grok-4.7", "input": "the prompt"} and sent["timeout"] >= reviewer.GROK_TIMEOUT_S
