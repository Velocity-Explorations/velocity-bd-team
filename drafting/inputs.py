"""What the worker's steps know about a pursued call, from the ledger (PRO-577).

    record = gather(pursuit_id)
    facts = call_facts(record, today)      # the block every Qualify prompt starts with
    inputs = draft_inputs(record)          # the reference pipeline's DraftInputs, for its phases

The ledger holds what the scanner saved (the call's text and details), both judges' reasons, the
team's votes and notes, the owner's choices at Start the draft, and the Proposal Library's
Register. The worker cannot open portal pages or download attachments yet, so the call's text is
what the scanner saved. Login-gated text goes to the model and the local files, never to logs.
Velocity's own facts come from 01 Company Reference on Drive, read again for every step
(drafting/facts.py); every prompt carries them as the only source for claims about the company.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from drafting.dates import deadline_day
from drafting.facts import Facts
from drafting.facts import load as load_facts
from drafting.pipeline import DraftInputs
from ledger import queries as lq

PAST_WORK_LIMIT = 8
DETAILS_CHARS = 20_000
CLOSING_NEAR_DAYS = 7
# The template each format calls for, as an opportunity type the reference's TEMPLATE_MAP knows.
FORMAT_TYPES = {"RFI response": "RFI", "SBIR or STTR technical volume": "SBIR", "White paper": "OTA",
                "Full proposal": "Solicitation"}
STOP_WORDS = {"the", "and", "for", "with", "from", "into", "this", "that", "phase", "call", "notice", "sources", "sought"}


@dataclass
class CallRecord:
    pursuit: dict[str, Any]
    call: dict[str, Any]
    judges: dict[str, dict[str, Any]]
    decisions: list[dict[str, Any]]
    past_work: list[dict[str, Any]]
    clashes: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    material: list[dict[str, Any]] = field(default_factory=list)   # what people added on the workspace (PW4)
    facts: Facts | None = None   # Velocity's facts, read from Drive for this step


def _json_list(value: Any) -> list[Any]:
    try:
        found = json.loads(value) if isinstance(value, str) else value
    except ValueError:
        return []
    return found if isinstance(found, list) else []


def _extra(call: dict[str, Any]) -> dict[str, Any]:
    try:
        found = json.loads(call.get("extra") or "{}")
    except ValueError:
        return {}
    return found if isinstance(found, dict) else {}


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9]+", (text or "").lower()) if len(w) > 2 and w not in STOP_WORDS}


def _relevance(proposal: dict[str, Any], call: dict[str, Any]) -> float:
    """How useful a past submission is likely to be: the same agency, an exemplar, a win, its strength,
    and words its title shares with the call's."""
    score = 0.0
    agency, department = (proposal.get("agency") or "").lower().strip(), (call.get("department") or "").lower()
    if agency and (agency in department or department and department in agency):
        score += 3
    score += 2 if proposal.get("use_as_exemplar") else 0
    score += 1 if proposal.get("outcome") == "won" else 0
    score += (proposal.get("strength_rating") or 0) / 5
    score += 0.5 * len(_words(proposal.get("title") or "") & _words(call.get("title") or ""))
    return score


def _solicitation_numbers(call: dict[str, Any]) -> set[str]:
    return {str(v).strip().lower() for k, v in _extra(call).items() if "solicitation" in k and isinstance(v, str) and v.strip()}


def _clashes(call: dict[str, Any], register: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """The same call on another portal, other pursued calls closing within a week of this one, and earlier
    submissions to the same solicitation in the Register (PW6, task 6)."""
    due = deadline_day(call.get("due_date"))
    near = []
    for other in lq.pursued_calls(exclude_id=call["id"]):
        day = deadline_day(other.get("due_date"))
        if due and day and abs((day - due).days) <= CLOSING_NEAR_DAYS:
            near.append(other)
    numbers, title = _solicitation_numbers(call), (call.get("title") or "").strip().lower()
    earlier = [p for p in register if (p.get("solicitation_id") or "").strip().lower() in numbers
               or (title and (p.get("title") or "").strip().lower() == title)]
    return {"same_title": lq.calls_titled(call.get("title") or "", exclude_id=call["id"]), "closing_near": near,
            "register": earlier}


def gather(pursuit_id: int) -> CallRecord:
    """Everything the ledger knows about a pursuit's call."""
    pursuit = lq.get_pursuit(pursuit_id)
    if pursuit is None:
        raise KeyError(f"no pursuit {pursuit_id}")
    call = lq.get_call(pursuit["call_id"])
    if call is None:
        raise KeyError(f"no call {pursuit['call_id']}")
    register = lq.list_proposals()
    ranked = sorted(register, key=lambda p: (-_relevance(p, call), p.get("submission_id") or ""))
    return CallRecord(pursuit=pursuit, call=call, judges=lq.latest_judgments(call["id"]),
                      decisions=lq.decision_history(call["id"]), past_work=ranked[:PAST_WORK_LIMIT],
                      clashes=_clashes(call, register),
                      material=[e for e in lq.pursuit_events(pursuit_id) if e["kind"] == "material"],
                      facts=load_facts())


def details_text(record: CallRecord) -> str:
    """The call's text as the scanner saved it, then the portal's details."""
    call = record.call
    lines = [(call.get("description") or "").strip()]
    details = [f"- {key}: {value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)}"
               for key, value in _extra(call).items() if value not in (None, "", [], {})]
    if details:
        lines += ["", "Details the portal gives:", *details]
    return "\n".join(lines).strip()[:DETAILS_CHARS]


def judges_text(record: CallRecord) -> str:
    claude = record.judges.get("claude") or {"verdict": record.call.get("ai_verdict"), "reasoning": record.call.get("ai_reasoning")}
    lines = []
    for name, judged in (("Claude", claude), ("Grok", record.judges.get("grok"))):
        if judged and judged.get("verdict"):
            lines.append(f"- {name}: {judged['verdict']}. {judged.get('reasoning') or ''}".rstrip())
        else:
            lines.append(f"- {name}: no verdict")
    return "\n".join(lines)


def team_text(record: CallRecord) -> str:
    """Each person's decision with its note, then the notes on the call."""
    lines = [f"- {d['decided_by']}: {d['status']} ({(d.get('decided_at') or '')[:10]})" + (f": {d['note']}" if d.get("note") else "")
             for d in record.decisions]
    notes = [line for line in (record.call.get("human_notes") or "").splitlines() if line.strip()]
    if notes:
        lines += ["", "Notes:", *(f"- {line}" for line in notes)]
    return "\n".join(lines) or "(no votes or notes)"


def past_work_text(record: CallRecord) -> str:
    lines = []
    for p in record.past_work:
        bits = [p.get("type"), p.get("agency"), f"submitted {p['submitted_date']}" if p.get("submitted_date") else None,
                f"outcome {p['outcome']}" if p.get("outcome") else None,
                f"strength {p['strength_rating']}/5" if p.get("strength_rating") else None,
                "exemplar" if p.get("use_as_exemplar") else None]
        line = f"- {p['submission_id']}: {p.get('title') or ''} ({', '.join(b for b in bits if b)})"
        extra = " ".join(x for x in (p.get("why_won_or_lost"), p.get("brief")) if x)
        lines.append(f"{line}. {extra}" if extra else line)
    return "\n".join(lines) or "(the Register has no past submissions)"


def builds_on_text(record: CallRecord) -> str:
    chosen = [str(item.get("name") or item.get("id")) for item in _json_list(record.pursuit.get("builds_on")) if isinstance(item, dict)]
    return "\n".join(f"- {name}" for name in chosen) or "(none chosen)"


def clashes_text(record: CallRecord) -> str:
    c = record.clashes
    lines = [f"- The same title on {x['portal']}: {x['id']}, due {x.get('due_date') or 'not given'}" for x in c.get("same_title", [])]
    lines += [f"- Also pursued, closing near the same date: {x['title']} ({x['portal']}), due {x.get('due_date')}" for x in c.get("closing_near", [])]
    lines += [f"- Submitted before to the same solicitation: {x['submission_id']} ({x.get('outcome') or 'no outcome'})" for x in c.get("register", [])]
    return "\n".join(lines) or "(no clashes found in the ledger)"


def call_facts(record: CallRecord, today: date) -> str:
    """The call, the dashboard's record and the owner's choices, for a step's prompt."""
    call, pursuit = record.call, record.pursuit
    working_with = ", ".join(str(x) for x in _json_list(pursuit.get("collaborators"))) or "nobody else"
    return "\n".join([
        "THE CALL",
        f"- Title: {call.get('title') or call['id']}",
        f"- Portal: {call.get('portal')}",
        f"- Type: {call.get('type') or 'not given'}",
        f"- Agency: {call.get('department') or 'not given'}",
        f"- Deadline, as the portal wrote it: {call.get('due_date') or 'not given'}",
        f"- Call page: {call.get('url') or 'not given'}",
        f"- Format to write: {pursuit.get('format') or 'not chosen'}",
        f"- Owner: {pursuit['owner']}; working with: {working_with}",
        f"- Today: {today.isoformat()}",
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
        "THE OWNER'S DIRECTION",
        (pursuit.get("direction") or "").strip() or "(none given)",
        "",
        "PAST WORK THE OWNER CHOSE TO BUILD ON",
        builds_on_text(record),
        "",
        "PAST SUBMISSIONS IN THE PROPOSAL REGISTER, MOST RELEVANT FIRST",
        past_work_text(record),
        *material_lines(record),
        *(["", record.facts.block(hoverslam_bid(record))] if record.facts else []),
    ])


def hoverslam_bid(record: CallRecord) -> bool:
    """Whether the bid goes in as Hoverslam Designs LLC: the owner's direction, or material the team added, says so.
    Otherwise the proposing company is Velocity Explorations and Hoverslam's facts stay out of the prompts."""
    said = [record.pursuit.get("direction") or "", *(str(m.get("text") or "") for m in record.material)]
    return any("hoverslam" in text.lower() for text in said)


def material_lines(record: CallRecord) -> list[str]:
    """The notes and links people added on the workspace (Add material, PW4), oldest first."""
    if not record.material:
        return []
    return ["", "MATERIAL THE TEAM ADDED"] + [f"- {(m.get('at') or '')[:10]} {m['who']}: {m['text']}" for m in record.material]


def draft_inputs(record: CallRecord) -> DraftInputs:
    """The reference pipeline's inputs for this call, so its phases can run on it."""
    call, pursuit = record.call, record.pursuit
    notes = team_text(record)
    if (pursuit.get("direction") or "").strip():
        notes += f"\n\nThe owner's direction: {pursuit['direction'].strip()}"
    return DraftInputs.from_dict({
        "title": call.get("title") or call["id"],
        "portal": call.get("portal") or "",
        "opp_type": FORMAT_TYPES.get(pursuit.get("format") or "", call.get("type") or ""),
        "agency": call.get("department") or "",
        "due_date": call.get("due_date") or "",
        "url": call.get("url") or "",
        "description": call.get("description") or "",
        "listing_text": details_text(record),
        "past_experience": past_work_text(record),
        "company_context": record.facts.block(hoverslam_bid(record)) if record.facts else "",
        "team_notes": notes,
    })
