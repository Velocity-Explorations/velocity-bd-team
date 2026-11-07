"""Grok with function tools, for Ask Grok (David, 7 Nov 2026).

    turn = GrokChat().respond(items, tool_defs)   # Turn(text, calls, items, tokens)

xAI's Responses API over urllib, asked not to store anything (store false), so every call carries the whole exchange:
the conversation, then each tool call Grok made with its result. A turn either asks for tools (calls, with the items to
send back beside their results) or answers (text). One more try after a rate limit, a timeout or a server error. The
key is BD_XAI_API_KEY, never XAI_API_KEY: on David's PC that name holds another project's key.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

log = logging.getLogger("assistant.grok")

XAI_URL = "https://api.x.ai/v1/responses"
MODEL_ID = "grok-4.7"   # the key is limited to this model
TIMEOUT_S = 120.0
TRANSIENT = (408, 429, 500, 502, 503, 504)
RETRY_DELAY_S = 2.0
_open = urllib.request.urlopen   # tests put a fake reply here


class GrokError(RuntimeError):
    """Grok gave no usable answer, after one more try where that was worth it."""


class _Transient(Exception):
    pass


@dataclass
class Turn:
    text: str                                   # the answer, when Grok asks for no tool
    calls: list[dict[str, Any]] = field(default_factory=list)   # {"call_id", "name", "arguments": dict}
    items: list[dict[str, Any]] = field(default_factory=list)   # the function_call items to send back with the results
    input_tokens: int = 0                       # not counting the cached part
    cached_tokens: int = 0
    output_tokens: int = 0


def _parse(body: dict[str, Any]) -> Turn:
    calls: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = []
    texts: list[str] = []
    for item in body.get("output") or []:
        kind = item.get("type")
        if kind == "function_call":
            items.append(item)
            try:
                arguments = json.loads(item.get("arguments") or "{}")
            except ValueError:
                arguments = {}
            calls.append({"call_id": item.get("call_id"), "name": item.get("name"),
                          "arguments": arguments if isinstance(arguments, dict) else {}})
        elif kind == "message":
            texts += [str(part.get("text") or "") for part in item.get("content") or [] if part.get("type") == "output_text"]
    usage = body.get("usage") or {}
    cached = int((usage.get("input_tokens_details") or {}).get("cached_tokens") or 0)
    return Turn(text="".join(texts).strip(), calls=calls, items=items,
                input_tokens=max(int(usage.get("input_tokens") or 0) - cached, 0), cached_tokens=cached,
                output_tokens=int(usage.get("output_tokens") or 0))


class GrokChat:
    def __init__(self, model: str = MODEL_ID) -> None:
        self.model = model

    def _once(self, body: dict[str, Any]) -> dict[str, Any]:
        from config import require

        request = urllib.request.Request(XAI_URL, data=json.dumps(body).encode("utf-8"), method="POST", headers={
            "Authorization": f"Bearer {require('BD_XAI_API_KEY')}", "Content-Type": "application/json"})
        try:
            with _open(request, timeout=TIMEOUT_S) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            if exc.code in TRANSIENT:
                raise _Transient(f"xAI answered {exc.code}") from exc
            raise GrokError(f"xAI answered {exc.code}") from exc
        except (OSError, ValueError) as exc:   # unreachable, timed out, or not JSON
            raise _Transient(f"xAI could not be read ({type(exc).__name__})") from exc

    def respond(self, items: list[dict[str, Any]], tool_defs: list[dict[str, Any]]) -> Turn:
        """One turn of the conversation: Grok's tool calls, or its answer."""
        body: dict[str, Any] = {"model": self.model, "input": items, "store": False}
        if tool_defs:
            body["tools"] = tool_defs
        problem = ""
        for attempt in (1, 2):
            started = time.monotonic()
            try:
                turn = _parse(self._once(body))
            except _Transient as exc:
                problem = str(exc)
            else:
                log.info("Grok turn: %d tool call(s), %d chars, %d tokens in (%d cached), %d out, %.1fs", len(turn.calls),
                         len(turn.text), turn.input_tokens, turn.cached_tokens, turn.output_tokens, time.monotonic() - started)
                if turn.calls or turn.text:
                    return turn
                problem = "Grok returned nothing"
            log.warning("Grok attempt %d failed: %s", attempt, problem)
            if attempt == 1:
                time.sleep(RETRY_DELAY_S)
        raise GrokError(f"{problem} (2 attempts)")
