"""The Writer's model client: streaming, one retry, clear failures, abortable (Writer Plan W0)."""
from __future__ import annotations

import json
import logging
import threading
import urllib.error
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


# ------------------------------------------------------------------------------ Grok, through xAI (29 Oct)

def sse(*events: dict[str, Any]) -> list[bytes]:
    """xAI's stream as it arrives: an event line, a data line and a blank line per event."""
    lines: list[bytes] = []
    for event in events:
        lines += [f"event: {event['type']}\n".encode(), f"data: {json.dumps(event)}\n".encode(), b"\n"]
    return lines


def delta(text: str) -> dict[str, Any]:
    return {"type": "response.output_text.delta", "delta": text}


def completed(status: str = "completed", prompt: int = 1_253, cached: int = 1_152, out: int = 68) -> dict[str, Any]:
    return {"type": f"response.{status}", "response": {"id": "resp_test", "status": status, "usage": {
        "input_tokens": prompt, "input_tokens_details": {"cached_tokens": cached}, "output_tokens": out}}}


class FakeResponse:
    def __init__(self, lines: list[bytes], gate: threading.Event | None = None) -> None:
        self.lines, self.gate, self.closed = lines, gate, False

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, *exc: Any) -> bool:
        self.closed = True
        return False

    def __iter__(self) -> Any:
        for line in self.lines:
            if self.gate is not None:
                self.gate.wait(2)
            if self.closed:
                raise ValueError("I/O operation on closed file")
            yield line

    def close(self) -> None:
        self.closed = True


class FakeXai:
    """Stands in for urlopen on xAI's Responses API: a scripted response, or an error, per call."""

    def __init__(self, script: list[Any]) -> None:
        self.script, self.requests = list(script), []

    def __call__(self, request: Any, timeout: float | None = None) -> FakeResponse:
        self.requests.append(request)
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def http_error(code: int) -> urllib.error.HTTPError:
    return urllib.error.HTTPError("https://api.x.ai/v1/responses", code, "error", {}, None)  # type: ignore[arg-type]


@pytest.fixture
def xai(monkeypatch: pytest.MonkeyPatch) -> Any:
    def install(*script: Any) -> FakeXai:
        fake = FakeXai(list(script))
        monkeypatch.setattr(llm, "_open", fake)
        monkeypatch.setenv("BD_XAI_API_KEY", "bd-test-key")
        monkeypatch.setenv("XAI_API_KEY", "another-projects-key")
        return fake
    return install


def test_the_writer_drafts_with_sonnet_unless_WRITER_MODEL_names_another(monkeypatch: pytest.MonkeyPatch) -> None:
    assert llm.writer_model() == "claude-sonnet-5-5"
    monkeypatch.setenv("WRITER_MODEL", " grok-4.7 ")
    assert llm.writer_model() == "grok-4.7"


def test_a_grok_model_streams_from_xai_with_the_velocity_key(xai: Any, caplog: pytest.LogCaptureFixture) -> None:
    fake = xai(FakeResponse(sse(delta("Hello "), delta("world"), completed())))
    seen: list[llm.Usage] = []
    with caplog.at_level(logging.INFO, logger="drafting.llm"):
        text = llm.generate("SECRET PROMPT TEXT", system="SYS", model="grok-4.7", phase_label="draft", max_tokens=1234,
                            on_usage=seen.append)
    assert text == "Hello world"
    request = fake.requests[0]
    assert request.full_url == "https://api.x.ai/v1/responses"
    assert request.get_header("Authorization") == "Bearer bd-test-key"   # never XAI_API_KEY
    assert json.loads(request.data) == {"model": "grok-4.7", "max_output_tokens": 1234, "stream": True, "store": False,
                                        "input": [{"role": "system", "content": "SYS"},
                                                  {"role": "user", "content": "SECRET PROMPT TEXT"}]}
    usage = seen[0]
    assert (usage.model, usage.input_tokens, usage.cache_read_tokens, usage.cache_write_tokens, usage.output_tokens,
            usage.truncated, usage.request_id) == ("grok-4.7", 101, 1_152, 0, 68, False, "resp_test")
    assert "draft" in caplog.text and "SECRET PROMPT TEXT" not in caplog.text


def test_WRITER_MODEL_grok_sends_every_call_to_xai(xai: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRITER_MODEL", "grok-4.7")
    fake = xai(FakeResponse(sse(delta("ok"), completed())))
    assert llm.generate("p") == "ok"
    assert json.loads(fake.requests[0].data)["model"] == "grok-4.7"
    assert "system" not in [m["role"] for m in json.loads(fake.requests[0].data)["input"]]


def test_grok_rate_limits_and_server_errors_are_retried_once(xai: Any) -> None:
    fake = xai(http_error(429), FakeResponse(sse(delta("second try"), completed())))
    assert llm.generate("p", model="grok-4.7", phase_label="draft") == "second try"
    assert len(fake.requests) == 2
    xai(http_error(503), http_error(503))
    with pytest.raises(llm.PhaseError, match=r"outline: xAI answered 503 \(2 attempts\)"):
        llm.generate("p", model="grok-4.7", phase_label="outline")


def test_a_bad_grok_request_fails_at_once(xai: Any) -> None:
    fake = xai(http_error(400), FakeResponse(sse(delta("unused"), completed())))
    with pytest.raises(llm.PhaseError, match="draft: xAI answered 400"):
        llm.generate("p", model="grok-4.7", phase_label="draft")
    assert len(fake.requests) == 1


def test_a_grok_stream_that_fails_or_stops_early_is_tried_once_more(xai: Any) -> None:
    xai(FakeResponse(sse(delta("half"))), FakeResponse(sse(delta("whole"), completed())))
    assert llm.generate("p", model="grok-4.7") == "whole"
    xai(FakeResponse(sse({"type": "response.failed", "response": {"status": "failed"}})),
        FakeResponse(sse(delta("again"), completed())))
    assert llm.generate("p", model="grok-4.7") == "again"


def test_a_grok_answer_cut_off_at_max_tokens_is_marked_truncated(xai: Any) -> None:
    xai(FakeResponse(sse(delta("cut off"), completed(status="incomplete"))))
    seen: list[llm.Usage] = []
    assert llm.generate("p", model="grok-4.7", on_usage=seen.append) == "cut off"
    assert seen[0].truncated


def test_an_empty_grok_answer_is_retried_then_fails(xai: Any) -> None:
    xai(FakeResponse(sse(completed())), FakeResponse(sse(delta("  "), completed())))
    with pytest.raises(llm.PhaseError, match="empty"):
        llm.generate("p", model="grok-4.7", phase_label="checklist")


def test_a_grok_stream_can_be_aborted_from_another_thread(xai: Any) -> None:
    gate = threading.Event()
    token = llm.AbortToken()
    xai(FakeResponse(sse(delta("a"), delta("b"), completed()), gate=gate))
    errors: list[BaseException] = []

    def run() -> None:
        try:
            llm.generate("p", model="grok-4.7", abort=token)
        except BaseException as exc:   # noqa: BLE001 (collected for the assertion)
            errors.append(exc)

    worker = threading.Thread(target=run)
    worker.start()
    token.set()
    gate.set()
    worker.join(5)
    assert not worker.is_alive() and len(errors) == 1 and isinstance(errors[0], llm.DraftCancelled)
