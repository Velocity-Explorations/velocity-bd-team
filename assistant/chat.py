"""Ask Grok's conversation (David, 7 Nov 2026): one question answered with read-only tools.

    reply = answer(question, history, page, model, tools, asked_by="David Wood")

Grok gets the rules (SYSTEM), the thread's earlier exchanges, the question with the page it was asked from, and the
tools' definitions. It calls the tools it needs, each result goes back to it (cut to RESULT_CHARS), and after
MAX_ROUNDS of tools it must answer. The rules hold no facts: this repo is public, and Velocity's facts reach Grok only
through the company_facts tool run.py supplies, which leaves SENSITIVE items out.
"""
from __future__ import annotations

import json
import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import parse_qs, unquote, urlsplit

from assistant.grok import Turn
from assistant.tools import Tool, ToolError

log = logging.getLogger("assistant.chat")

MAX_ROUNDS = 6           # rounds of tool calls before Grok must answer
RESULT_CHARS = 6000      # the most of one tool's result Grok reads
HISTORY = 8              # earlier exchanges of the thread it is reminded of
FACT_ID = re.compile(r"\b(?:F|PP|PR|PE)-\d+[a-z]?\b")

SYSTEM = """You are Ask Grok, the assistant on Velocity Explorations' business development dashboard. The team asks you about the calls the dashboard lists (solicitations, RFIs, CSOs, BAAs and announcements found by its scans), about Velocity, and about Velocity's past bids and past performance.

Rules:
- Answer only from what your tools return. Before you say anything about a call, about Velocity or about a past bid, call a tool for it; never answer such things from memory.
- Velocity's facts come only from company_facts. Cite the id of each fact you use, such as F-06 or PP-20. Where the record says nothing, write NEEDS FACT: followed by what is missing, and never guess.
- A fact marked OPEN or EVIDENCE PENDING is not settled: say so when you use it.
- Never state anything SENSITIVE (clearances, contract values, commercial pricing). The tools leave such items out; if asked, say it is not shared here.
- Never name a person the record says is not approved to name, or not to cite: say only that a contact exists, and leave the name out.
- Name each call by its title and give its deadline as the tool gives it. The person's current page may name the call they are looking at.
- You can read but cannot change anything. If someone asks you to decide a call, start a draft, change keywords or run a scan, say where on the dashboard they can do it.
- Answer briefly in plain words: short paragraphs, or bullets that start with "- ". No headings and no tables. Never use an en dash or an em dash.
- If someone pastes a password, a key or CUI, do not repeat it back."""


class Model(Protocol):
    def respond(self, items: list[dict[str, Any]], tool_defs: list[dict[str, Any]]) -> Turn: ...


@dataclass
class Reply:
    text: str
    sources: dict[str, Any] = field(default_factory=lambda: {"calls": [], "facts": []})
    trace: list[dict[str, Any]] = field(default_factory=list)
    input_tokens: int = 0
    cached_tokens: int = 0
    output_tokens: int = 0
    rounds: int = 0


def tool_defs(tools: Sequence[Tool]) -> list[dict[str, Any]]:
    """The tools as xAI's Responses API declares a function tool."""
    return [{"type": "function", "name": t.name, "description": t.description, "parameters": t.parameters} for t in tools]


def page_call(page: str | None) -> str | None:
    """The call open on the page a question was asked from: Calls' focus= or a proposal workspace."""
    if not page:
        return None
    parts = urlsplit(page)
    focus = parse_qs(parts.query).get("focus")
    if focus and focus[0]:
        return focus[0]
    segments = [s for s in parts.path.split("/") if s]
    if len(segments) >= 2 and segments[0] == "proposals" and segments[1] not in ("submitted", "results"):
        return unquote(segments[1])
    return None


def _opening(question: str, page: str | None, asked_by: str) -> str:
    where = f"{asked_by or 'A team member'} is asking"
    if page:
        where += f", from the dashboard page {page}"
        call = page_call(page)
        if call:
            where += f", where the call open is {call}"
    return f"{where}.\n\n{question}"


def _run(tool: Tool | None, name: str, arguments: dict[str, Any]) -> tuple[str, dict[str, Any] | None]:
    if tool is None:
        return f"There is no tool called {name}.", None
    try:
        result = tool.run(**arguments)
    except ToolError as exc:
        return f"The tool said: {exc}", None
    except TypeError as exc:   # arguments the tool does not take
        return f"The tool could not run with those arguments: {exc}", None
    except Exception as exc:   # never let one tool stop the answer
        log.warning("Tool %s failed: %s: %s", name, type(exc).__name__, str(exc)[:200])
        return f"The tool failed ({type(exc).__name__}).", None
    text = str(result.get("text") or "") if isinstance(result, dict) else ""
    if not text:
        text = json.dumps(result, default=str)
    if len(text) > RESULT_CHARS:
        text = text[:RESULT_CHARS] + "\n(cut short)"
    return text, result if isinstance(result, dict) else None


def _call_refs(value: Any) -> list[dict[str, Any]]:
    """Every call a tool's result names: a dict with an id, a title and a portal."""
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if {"id", "title", "portal"} <= set(value):
            found.append({"id": value["id"], "title": value["title"], "portal": value["portal"]})
        for v in value.values():
            found += _call_refs(v)
    elif isinstance(value, list):
        for v in value:
            found += _call_refs(v)
    return found


def _sources(text: str, results: list[dict[str, Any]]) -> dict[str, Any]:
    """The calls the answer names, by title or id, and the Company Reference ids it cites."""
    lowered = text.lower()
    calls: list[dict[str, Any]] = []
    for ref in (r for result in results for r in _call_refs(result)):
        named = str(ref["id"]).lower() in lowered or (str(ref["title"] or "").strip() and str(ref["title"]).lower() in lowered)
        if named and ref["id"] not in [c["id"] for c in calls]:
            calls.append(ref)
    return {"calls": calls[:8], "facts": list(dict.fromkeys(FACT_ID.findall(text)))}


def answer(question: str, history: Sequence[tuple[str, str]], page: str | None, model: Model, tools: Sequence[Tool],
           asked_by: str = "") -> Reply:
    """Grok's answer to one question, with the tools it called, what it cites and the tokens it took."""
    by_name = {t.name: t for t in tools}
    defs = tool_defs(tools)
    items: list[dict[str, Any]] = [{"role": "system", "content": SYSTEM}]
    for asked, said in list(history)[-HISTORY:]:
        items += [{"role": "user", "content": asked}, {"role": "assistant", "content": said}]
    items.append({"role": "user", "content": _opening(question, page, asked_by)})
    reply = Reply(text="")
    results: list[dict[str, Any]] = []
    while True:
        last = reply.rounds >= MAX_ROUNDS
        turn = model.respond(items, [] if last else defs)
        reply.rounds += 1
        reply.input_tokens += turn.input_tokens
        reply.cached_tokens += turn.cached_tokens
        reply.output_tokens += turn.output_tokens
        if not turn.calls or last:
            reply.text = turn.text or "Grok gave no answer. Try asking again."
            reply.sources = _sources(reply.text, results)
            return reply
        items += turn.items
        for call in turn.calls:
            name, arguments = str(call.get("name") or ""), call.get("arguments") or {}
            output, result = _run(by_name.get(name), name, arguments)
            if result is not None:
                results.append(result)
            reply.trace.append({"name": name, "arguments": arguments, "chars": len(output)})
            items.append({"type": "function_call_output", "call_id": call.get("call_id"), "output": output})
