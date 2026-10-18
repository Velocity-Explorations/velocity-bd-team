"""The Writer's model client: streaming, one retry, clear failures, abortable (Writer Plan W0)."""
from __future__ import annotations

import logging
import threading
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2 as httpx   # the HTTP library this SDK version uses
import pytest

from drafting import llm

REQUEST = httpx.Request("POST", "https://api.anthropic.com/v1/messages")


def final(stop: str = "end_turn", out_tokens: int = 5) -> SimpleNamespace:
    usage = SimpleNamespace(input_tokens=11, output_tokens=out_tokens, cache_read_input_tokens=0,
                            cache_creation_input_tokens=0)
    return SimpleNamespace(stop_reason=stop, usage=usage, _request_id="req_test")


class FakeStream:
    def __init__(self, chunks: list[str], message: SimpleNamespace, gate: threading.Event | None = None) -> None:
        self.chunks, self.message, self.gate, self.closed = chunks, message, gate, False

    def __enter__(self) -> "FakeStream":
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.closed = True
        return False

    @property
    def text_stream(self) -> Any:
        for chunk in self.chunks:
            if self.gate is not None:
                self.gate.wait(2)
            if self.closed:
                raise httpx.ReadError("stream closed", request=REQUEST)
            yield chunk

    def get_final_message(self) -> SimpleNamespace:
        return self.message

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(self, script: list[Any]) -> None:
        self.script, self.calls = list(script), []
        self.messages = self

    def stream(self, **kwargs: Any) -> FakeStream:
        self.calls.append(kwargs)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


@pytest.fixture(autouse=True)
def no_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(llm.time, "sleep", lambda s: None)


def test_generate_streams_the_text_and_reports_usage(caplog: pytest.LogCaptureFixture) -> None:
    client = FakeClient([FakeStream(["Hello ", "world"], final())])
    seen: list[llm.Usage] = []
    with caplog.at_level(logging.INFO, logger="drafting.llm"):
        text = llm.generate("SECRET PROMPT TEXT", system="SYS", phase_label="requirements", client=client,
                            on_usage=seen.append, max_tokens=1234)
    assert text == "Hello world"
    call = client.calls[0]
    assert call["model"] == llm.DEFAULT_MODEL == "claude-sonnet-5-5" and call["max_tokens"] == 1234
    assert call["system"] == "SYS" and call["messages"] == [{"role": "user", "content": "SECRET PROMPT TEXT"}]
    assert seen[0].input_tokens == 11 and seen[0].output_tokens == 5 and not seen[0].truncated
    assert "requirements" in caplog.text and "SECRET PROMPT TEXT" not in caplog.text


def test_no_system_prompt_is_sent_when_empty() -> None:
    client = FakeClient([FakeStream(["ok"], final())])
    llm.generate("p", client=client, model="claude-haiku-5-5")
    assert "system" not in client.calls[0] and client.calls[0]["model"] == "claude-haiku-5-5"


def test_a_transient_error_is_retried_once() -> None:
    client = FakeClient([anthropic.APIConnectionError(request=REQUEST), FakeStream(["second try"], final())])
    assert llm.generate("p", client=client, phase_label="draft") == "second try"
    assert len(client.calls) == 2


def test_two_failures_raise_a_phase_error_naming_the_phase() -> None:
    client = FakeClient([anthropic.APIConnectionError(request=REQUEST), anthropic.APIConnectionError(request=REQUEST)])
    with pytest.raises(llm.PhaseError, match="outline"):
        llm.generate("p", client=client, phase_label="outline")


def test_empty_output_is_retried_then_fails() -> None:
    client = FakeClient([FakeStream([], final()), FakeStream(["  "], final())])
    with pytest.raises(llm.PhaseError, match="empty"):
        llm.generate("p", client=client, phase_label="checklist")


def test_a_refusal_fails_without_retrying() -> None:
    client = FakeClient([FakeStream(["no"], final(stop="refusal")), FakeStream(["unused"], final())])
    with pytest.raises(llm.PhaseError, match="refused"):
        llm.generate("p", client=client, phase_label="draft")
    assert len(client.calls) == 1


def test_hitting_max_tokens_returns_the_text_marked_truncated() -> None:
    seen: list[llm.Usage] = []
    client = FakeClient([FakeStream(["cut off"], final(stop="max_tokens"))])
    assert llm.generate("p", client=client, on_usage=seen.append) == "cut off"
    assert seen[0].truncated


def test_a_stream_can_be_aborted_from_another_thread() -> None:
    gate = threading.Event()
    token = llm.AbortToken()
    client = FakeClient([FakeStream(["a", "b", "c"], final(), gate=gate)])
    errors: list[BaseException] = []

    def run() -> None:
        try:
            llm.generate("p", client=client, abort=token)
        except BaseException as exc:   # noqa: BLE001 (collected for the assertion)
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    token.set()
    gate.set()
    worker.join(5)
    assert not worker.is_alive() and len(errors) == 1 and isinstance(errors[0], llm.DraftCancelled)
    assert token.is_set()
