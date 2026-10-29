"""The Writer's model client: Claude through the Anthropic API, or Grok through xAI's Responses API for a
grok model (WRITER_MODEL picks the model), streamed, with one retry and an abort handle.

    text = generate(prompt, system, phase_label="drafting response", max_tokens=48_000)

Replaces the reference's `claude -p` subprocess. Responses stream, so a long phase never
leaves a connection idle. A transient failure (connection, rate limit, server error, empty
answer) is retried once; anything else raises PhaseError naming the phase. Prompt text is
logged only at DEBUG; INFO gets lengths, tokens and seconds. An AbortToken set from another
thread closes the stream in flight and raises DraftCancelled, so a cancelled draft stops
spending at once (Writer Plan W2a). Grok calls use BD_XAI_API_KEY and ask xAI not to store them.
"""
from __future__ import annotations

import json
import logging
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import anthropic

log = logging.getLogger("drafting.llm")

DEFAULT_MODEL = "claude-sonnet-5-5"
RETRY_DELAY_S = 2.0
READ_TIMEOUT_S = 300.0   # longest silence tolerated mid-stream; the call's own cap is `timeout`
# Claude thinks before it answers, and the thinking counts against max_tokens. A call's max_tokens is room for its
# answer; generate adds THINKING_ROOM on top, up to the Messages API's output limit.
THINKING_ROOM = 32_000
MAX_OUTPUT_TOKENS = 128_000
TRANSIENT = tuple(getattr(anthropic, name) for name in (
    "APIConnectionError", "RateLimitError", "InternalServerError", "OverloadedError",
    "ServiceUnavailableError", "DeadlineExceededError", "RetryableError") if hasattr(anthropic, name))
XAI_URL = "https://api.x.ai/v1/responses"
XAI_READ_TIMEOUT_S = 600.0   # Grok may think in silence before its first word
XAI_TRANSIENT = (408, 429, 500, 502, 503, 504)
_open = urllib.request.urlopen   # tests put a fake stream here


class PhaseError(RuntimeError):
    """A model call that failed for good; the message starts with the phase label."""


class DraftCancelled(Exception):
    """The draft was cancelled while a call was in flight. Never caught by a phase."""


class _EmptyOutput(Exception):
    pass


class _Transient(Exception):
    """A Grok failure worth one more try: a rate limit, a server error, a stream that broke off."""


@dataclass
class Usage:
    phase_label: str
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    seconds: float
    truncated: bool
    request_id: str


class AbortToken:
    """Set from any thread to stop the call in flight and every call after it."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._lock = threading.Lock()
        self._stream: Any = None

    def set(self) -> None:
        self._event.set()
        with self._lock:
            stream = self._stream
        if stream is not None:
            try:
                stream.close()
            except Exception:   # noqa: BLE001 (closing a dying stream may fail; the flag is what counts)
                pass

    def is_set(self) -> bool:
        return self._event.is_set()

    def attach(self, stream: Any) -> None:
        with self._lock:
            self._stream = stream
        if self.is_set():
            self.set()

    def detach(self) -> None:
        with self._lock:
            self._stream = None


_client: Any = None


def writer_model() -> str:
    """The model every Writer call uses: WRITER_MODEL, else Claude Sonnet."""
    from config import get

    return (get("WRITER_MODEL") or "").strip() or DEFAULT_MODEL


def is_grok(model: str) -> bool:
    return model.startswith("grok-")


def default_client() -> Any:
    """The shared Anthropic client, keyed from ANTHROPIC_API_KEY. Retries are ours, not the SDK's."""
    global _client
    if _client is None:
        from config import require

        _client = anthropic.Anthropic(api_key=require("ANTHROPIC_API_KEY"), max_retries=0)
    return _client


def _usage(message: Any, label: str, model: str, seconds: float) -> Usage:
    u = getattr(message, "usage", None)

    def tokens(name: str) -> int:
        return int(getattr(u, name, 0) or 0)

    return Usage(phase_label=label, model=model, input_tokens=tokens("input_tokens"),
                 output_tokens=tokens("output_tokens"), cache_read_tokens=tokens("cache_read_input_tokens"),
                 cache_write_tokens=tokens("cache_creation_input_tokens"), seconds=round(seconds, 1),
                 truncated=getattr(message, "stop_reason", "") == "max_tokens",
                 request_id=str(getattr(message, "_request_id", "") or ""))


def _stream_once(client: Any, kwargs: dict[str, Any], label: str, timeout: float, abort: AbortToken | None,
                 on_usage: Callable[[Usage], None] | None) -> str:
    started = time.monotonic()
    parts: list[str] = []
    with client.messages.stream(**kwargs) as stream:
        if abort is not None:
            abort.attach(stream)
        try:
            for text in stream.text_stream:
                parts.append(text)
                if abort is not None and abort.is_set():
                    raise DraftCancelled(f"{label}: cancelled")
                if time.monotonic() - started > timeout:
                    raise PhaseError(f"{label}: no complete answer within {timeout:.0f}s")
            message = stream.get_final_message()
        finally:
            if abort is not None:
                abort.detach()
    usage = _usage(message, label, kwargs["model"], time.monotonic() - started)
    if getattr(message, "stop_reason", "") == "refusal":
        raise PhaseError(f"{label}: the model refused this request")
    if on_usage is not None:
        on_usage(usage)
    text = "".join(parts).strip()
    log.info("%s: %d chars out, %d tokens in, %d out, %.1fs%s", label, len(text), usage.input_tokens,
             usage.output_tokens, usage.seconds, " (hit max_tokens, output cut off)" if usage.truncated else "")
    if not text:
        raise _EmptyOutput()
    return text


def _xai_usage(final: dict[str, Any], label: str, model: str, seconds: float) -> Usage:
    usage = final.get("usage") or {}
    cached = int((usage.get("input_tokens_details") or {}).get("cached_tokens") or 0)
    return Usage(phase_label=label, model=model, input_tokens=max(int(usage.get("input_tokens") or 0) - cached, 0),
                 output_tokens=int(usage.get("output_tokens") or 0), cache_read_tokens=cached, cache_write_tokens=0,
                 seconds=round(seconds, 1), truncated=final.get("status") == "incomplete",
                 request_id=str(final.get("id") or ""))


def _xai_once(model: str, prompt: str, system: str, max_tokens: int, label: str, timeout: float,
              abort: AbortToken | None, on_usage: Callable[[Usage], None] | None) -> str:
    """One streamed Grok answer from xAI's Responses API, which is asked not to store it."""
    from config import require

    messages = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    body = {"model": model, "input": messages, "max_output_tokens": max_tokens, "stream": True, "store": False}
    request = urllib.request.Request(XAI_URL, data=json.dumps(body).encode("utf-8"), method="POST", headers={
        # BD_XAI_API_KEY, never XAI_API_KEY: on David's PC that name holds another project's key
        "Authorization": f"Bearer {require('BD_XAI_API_KEY')}", "Content-Type": "application/json",
        "Accept": "text/event-stream"})
    started = time.monotonic()
    try:
        response = _open(request, timeout=XAI_READ_TIMEOUT_S)
    except urllib.error.HTTPError as exc:
        if exc.code in XAI_TRANSIENT:
            raise _Transient(f"xAI answered {exc.code}") from exc
        raise PhaseError(f"{label}: xAI answered {exc.code}") from exc
    except OSError as exc:   # unreachable, refused or timed out
        raise _Transient(f"xAI could not be reached ({type(exc).__name__})") from exc
    parts: list[str] = []
    final: dict[str, Any] | None = None
    with response:
        if abort is not None:
            abort.attach(response)
        try:
            for raw in response:
                line = raw.decode("utf-8").strip()
                if not line.startswith("data:"):
                    continue
                event = json.loads(line[len("data:"):])
                kind = event.get("type")
                if kind == "response.output_text.delta":
                    parts.append(str(event.get("delta") or ""))
                elif kind in ("response.completed", "response.incomplete"):
                    final = event.get("response") or {}
                elif kind in ("response.failed", "error"):
                    raise _Transient(f"xAI reported {kind}")
                if abort is not None and abort.is_set():
                    raise DraftCancelled(f"{label}: cancelled")
                if time.monotonic() - started > timeout:
                    raise PhaseError(f"{label}: no complete answer within {timeout:.0f}s")
        except (DraftCancelled, PhaseError, _Transient):
            raise
        except Exception as exc:   # the stream closed by an abort, or dropped mid-answer
            if abort is not None and abort.is_set():
                raise DraftCancelled(f"{label}: cancelled") from exc
            raise _Transient(f"the xAI stream broke off ({type(exc).__name__})") from exc
        finally:
            if abort is not None:
                abort.detach()
    if final is None:
        raise _Transient("the xAI stream ended before its answer did")
    usage = _xai_usage(final, label, model, time.monotonic() - started)
    if on_usage is not None:
        on_usage(usage)
    text = "".join(parts).strip()
    log.info("%s: %d chars out, %d tokens in (%d cached), %d out, %.1fs%s", label, len(text), usage.input_tokens,
             usage.cache_read_tokens, usage.output_tokens, usage.seconds,
             " (hit max_tokens, output cut off)" if usage.truncated else "")
    if not text:
        raise _EmptyOutput()
    return text


def generate(prompt: str, system: str = "", model: str | None = None, max_tokens: int = 8000,
             timeout: float = 600, phase_label: str = "", *, abort: AbortToken | None = None,
             on_usage: Callable[[Usage], None] | None = None, client: Any = None) -> str:
    """The model's answer to one prompt, streamed. Raises PhaseError or DraftCancelled."""
    label = phase_label or "generating"
    model = model or writer_model()
    kwargs: dict[str, Any] = {"model": model, "max_tokens": min(max_tokens + THINKING_ROOM, MAX_OUTPUT_TOKENS),
                              "timeout": READ_TIMEOUT_S, "messages": [{"role": "user", "content": prompt}]}
    if system:
        kwargs["system"] = system
    log.info("%s: prompt %d chars, system %d chars, model %s", label, len(prompt), len(system), model)
    log.debug("%s system prompt:\n%s\n%s user prompt:\n%s", label, system, label, prompt)
    problem = ""
    for attempt in (1, 2):
        if abort is not None and abort.is_set():
            raise DraftCancelled(f"{label}: cancelled")
        try:
            if is_grok(model):
                return _xai_once(model, prompt, system, max_tokens, label, timeout, abort, on_usage)
            return _stream_once(client or default_client(), kwargs, label, timeout, abort, on_usage)
        except (DraftCancelled, PhaseError):
            raise
        except _EmptyOutput:
            problem = "the model returned empty output"
        except _Transient as exc:
            problem = str(exc)
        except TRANSIENT as exc:
            problem = f"{type(exc).__name__}: {str(exc)[:200]}"
        except anthropic.APIStatusError as exc:
            raise PhaseError(f"{label}: {type(exc).__name__} {exc.status_code}: {str(exc.message)[:200]}") from exc
        except Exception as exc:
            if abort is not None and abort.is_set():
                raise DraftCancelled(f"{label}: cancelled") from exc
            raise PhaseError(f"{label}: {type(exc).__name__}: {str(exc)[:200]}") from exc
        log.warning("%s: attempt %d failed: %s", label, attempt, problem)
        if attempt == 1:
            time.sleep(RETRY_DELAY_S)
    raise PhaseError(f"{label}: {problem} (2 attempts)")
