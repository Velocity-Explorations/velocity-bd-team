"""What Start the draft suggests (David, 7 Nov 2026): Claude, the Writer's model, recommends how to set a draft up.

    suggestion, dollars = suggest(call_id)   # {"format", "format_why", "approval_mode", "approval_why", "direction", "builds_on"}

It reads what the Writer reads before Discovery: the call as the scanner saved it, both judges' verdicts and the team's
notes, Velocity's facts (first in the request, so the API caches them), the Proposal Register ranked as the Writer ranks
it, and the Proposal Library's list, the past work the dialog offers to build on. The answer is checked before it is
kept: a format or approval mode not on the dialog's list is dropped, and so is any library id the list does not hold.
The person sees it filled in and changes anything before starting the draft. run.py --assistant runs it when the
dialog's Suggest button asks.
"""
from __future__ import annotations

import json
import re
from collections.abc import Iterable
from typing import Any

from drafting.costs import cost_of
from drafting.facts import load as load_facts
from drafting.inputs import CallRecord, _relevance, details_text, judges_text, team_text
from drafting.llm import Usage, generate, writer_model
from drafting.prompts import Prompt
from drafting.steps import fix_dashes
from ledger import queries as lq

FORMATS = ("White paper", "RFI response", "SBIR or STTR technical volume", "Full proposal", "Pitch deck", "Other")
APPROVAL_MODES = ("every_step", "key_gates")
FOLDER = "application/vnd.google-apps.folder"
REGISTER_ROWS = 15          # the most relevant Register rows the prompt shows in full
BUILDS_ON_MAX = 5
DIRECTION_CHARS = 2000      # the dialog's Direction box holds this much
WHY_CHARS = 240
MAX_TOKENS = 3000
TIMEOUT_S = 300.0
FENCED = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.S)


class SuggestionError(RuntimeError):
    """Claude's answer held no suggestion that could be read."""


SYSTEM = f"""You advise Velocity Explorations' business development team on how to set up a proposal draft before the Writer starts on it. Velocity's facts come first in this request and are the only source for claims about the company: cite each fact you rely on by its id (F-, PP-, PR-, PE-). Never invent a fact; where one the bid needs is missing, write NEEDS FACT: and what is missing.

Answer with one fenced json block and nothing else, in this shape:
{{"format": "...", "format_why": "...", "approval_mode": "...", "approval_why": "...", "direction": "...", "builds_on": [{{"id": "...", "why": "..."}}]}}

- format: exactly one of {", ".join(FORMATS)}: what the call asks the team to submit.
- format_why: one short sentence.
- approval_mode: "key_gates" when the bid is familiar ground close to past work and the deadline leaves room; "every_step" when it is new ground, large, unclear, or the deadline is near enough that a wrong turn would cost the bid.
- approval_why: one short sentence.
- direction: at most 1,200 characters of plain sentences, written to the Writer: the angle that answers what the buyer wants; the past performance and products to lead with, by id; a partner to name only if the facts show one fits; and the watch-outs (eligibility, CUI or CMMC, page or format limits, dates, anything the call rules out).
- builds_on: up to {BUILDS_ON_MAX} items from the PAST WORK list, most useful first, each by its id exactly as listed and with a one-line why. Only ids from that list.

Plain words. Never use an en dash or an em dash."""


def _library() -> list[dict[str, Any]]:
    """The past work the dialog offers: submission folders and Company Reference files."""
    found = []
    for item in lq.drive_items():
        path = str(item.get("path") or "")
        if item.get("mime") == FOLDER and re.fullmatch(r"02 Submissions/[^/]+", path):
            found.append(item)
        elif item.get("mime") != FOLDER and path.startswith("01 Company Reference/"):
            found.append(item)
    return found


def build_prompt(call: dict[str, Any]) -> Prompt:
    """The request for one call: the call, the judges and the team, then the past work it could build on."""
    register = lq.list_proposals()
    ranked = sorted(register, key=lambda p: (-_relevance(p, call), p.get("submission_id") or ""))
    record = CallRecord(pursuit={}, call=call, judges=lq.latest_judgments(call["id"]), decisions=lq.decision_history(call["id"]),
                        past_work=ranked[:REGISTER_ROWS])
    by_folder = {p["submission_id"]: p for p in register}
    rank = {p["submission_id"]: n for n, p in enumerate(ranked)}
    library = _library()
    folders = sorted((i for i in library if i.get("mime") == FOLDER), key=lambda i: (rank.get(i["name"], 10_000), i["name"]))
    files = [i for i in library if i.get("mime") != FOLDER]
    lines = []
    for item in folders:
        bid = by_folder.get(item["name"])
        about = ""
        if bid:
            bits = [bid.get("title"), bid.get("agency"), f"outcome {bid['outcome']}" if bid.get("outcome") else None,
                    bid.get("why_won_or_lost")]
            about = ": " + "; ".join(str(b) for b in bits if b)
        lines.append(f"- {item['id']} | {item['name']}{about}")
    lines += [f"- {item['id']} | {item['path']}" for item in files]
    call_lines = [
        "THE CALL",
        f"- Title: {call.get('title') or call['id']}",
        f"- Id: {call['id']}",
        f"- Portal: {call.get('portal')}",
        f"- Type: {call.get('type') or 'not given'}",
        f"- Agency: {call.get('department') or 'not given'}",
        f"- Deadline, as the portal wrote it: {call.get('due_date') or 'not given'}",
        "",
        "THE CALL'S TEXT, AS THE SCANNER SAVED IT",
        details_text(record) or "(no text saved)",
        "",
        "THE JUDGES' VERDICTS",
        judges_text(record),
        "",
        "THE TEAM'S VOTES AND NOTES",
        team_text(record),
        "",
        "PAST WORK THE DRAFT CAN BUILD ON (id | folder or file: what the Proposal Register says), most relevant first",
        "\n".join(lines) or "(the Proposal Library has not been indexed yet)",
    ]
    return Prompt(SYSTEM, "\n".join(call_lines))


def _text(value: Any, limit: int) -> str:
    return fix_dashes(" ".join(str(value or "").split()))[:limit]


def parse(answer: str, library_ids: Iterable[str]) -> dict[str, Any]:
    """The suggestion in Claude's answer, with anything the dialog cannot take left out. Raises SuggestionError."""
    match = FENCED.search(answer or "")
    try:
        found = json.loads(match.group(1) if match else answer)
    except (TypeError, ValueError) as exc:
        raise SuggestionError("Claude's answer held no suggestion that could be read") from exc
    if not isinstance(found, dict):
        raise SuggestionError("Claude's answer held no suggestion that could be read")
    allowed = set(library_ids)
    picks = []
    for item in found.get("builds_on") if isinstance(found.get("builds_on"), list) else []:
        if isinstance(item, dict) and str(item.get("id")) in allowed and str(item["id"]) not in [p["id"] for p in picks]:
            picks.append({"id": str(item["id"]), "why": _text(item.get("why"), WHY_CHARS)})
    return {
        "format": found.get("format") if found.get("format") in FORMATS else None,
        "format_why": _text(found.get("format_why"), WHY_CHARS),
        "approval_mode": found.get("approval_mode") if found.get("approval_mode") in APPROVAL_MODES else None,
        "approval_why": _text(found.get("approval_why"), WHY_CHARS),
        "direction": fix_dashes(str(found.get("direction") or "").strip())[:DIRECTION_CHARS],
        "builds_on": picks[:BUILDS_ON_MAX],
    }


def suggest(call_id: str) -> tuple[dict[str, Any], float]:
    """Claude's suggestion for one call, and what it cost in dollars."""
    call = lq.get_call(call_id)
    if call is None:
        raise SuggestionError(f"no call {call_id}")
    facts = load_facts()
    prompt = build_prompt(call)
    usages: list[Usage] = []
    answer = generate(prompt.user, prompt.system, model=writer_model(), max_tokens=MAX_TOKENS, timeout=TIMEOUT_S,
                      phase_label="draft suggestion", on_usage=usages.append, prefix=facts.block(False))
    return parse(answer, {i["id"] for i in _library()}), sum(cost_of(u) for u in usages)
