"""Each call the team pursues gets an issue in the Pursuits project of Velocity's Operations team on Linear, kept in
step with the call (David, 4 Nov 2026). `run.py --linear-sync` runs this at 08:07 and 13:07 (David, 5 Nov).

    changes = sync(LinearBoard(LinearClient()))   # ["c1: opened OPS-101", "c2: OPS-99 moved to Done", ...]

A call marked Pursue on the dashboard gets an issue in Backlog: what to submit and by when, due on the deadline,
assigned to whoever marked it, prioritised by the deadline, with Claude's summary, both judges, the portal's details
and links. The issue moves to In Progress when drafting starts and to Done when the call is marked Submitted; a
recorded result adds a comment; a withdrawn Pursue, a no-go or a closed draft cancels it with the reason. The sync acts
only when the call's stage moves on (linear_issues.stage), so a person may move an issue by hand meanwhile. A call
pursued again after its issue was canceled gets a new issue: Velocity's Linear rulebook never reopens a canceled one.
A call whose deadline has passed gets no issue.
Everything written is free of en and em dashes, as the house rule asks of anything written as David.
"""
from __future__ import annotations

import json
import re
import urllib.parse
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any, Protocol

from config import get
from drafting.dates import DASHBOARD_ZONE, deadline_day, parse_due
from ledger import queries as lq

STAGES = ("pursued", "drafting", "submitted", "result")   # the order a call moves through them
OPENS_AT = ("pursued", "drafting")
TITLE_MAX = 80
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
DECISIONS = {"pursue": "Pursue", "submitted": "Submitted", "not_relevant": "Not relevant", "dismissed": "Dismissed"}
RESULTS = {"won": "Won", "lost": "Lost", "withdrawn": "Withdrawn", "cancelled_by_agency": "Cancelled by the agency"}
EN_DASH, EM_DASH = chr(0x2013), chr(0x2014)
DASH = f"[{EN_DASH}{EM_DASH}]"
NAMED = re.compile(r"^(.*?)\s*<([^<>\s]+)>$")   # "Name <email>" in DASHBOARD_USERS


class Board(Protocol):
    def open(self, title: str, body: str, due: str | None, priority: int, assignee_email: str | None) -> dict[str, str] | None: ...
    def move(self, issue_id: str, state: str) -> bool: ...
    def comment(self, issue_id: str, body: str) -> bool: ...


def stage_of(row: Mapping[str, Any]) -> str:
    """Where the call stands: pursued, drafting, submitted, result, or withdrawn (no longer pursued)."""
    if row.get("result"):
        return "result"
    if row.get("pursuit_state") == "submitted" or row.get("human_status") == "submitted":
        return "submitted"
    if row.get("human_status") != "pursue" or row.get("pursuit_state") in ("no_go", "closed"):
        return "withdrawn"
    return "drafting" if row.get("pursuit_state") == "working" else "pursued"


def undash(text: str) -> str:
    """En and em dashes replaced as drafting/steps.py fix_dashes does: a number range reads "to", a dash opening a line
    becomes a hyphen, and any other becomes a comma."""
    text = re.sub(rf"(\d)\s*{DASH}\s*(\d)", r"\1 to \2", text)
    text = re.sub(rf"^(\s*){DASH}\s*", r"\1- ", text, flags=re.M)
    return re.sub(rf"\s*{DASH}\s*", ", ", text)


def day_text(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def _on(when: str | None) -> str:
    """" on 4 Nov 2026" for a timestamp or a bare date, in Denver like the dashboard; "" without one."""
    day = deadline_day(when) if when else None
    return f" on {day_text(day)}" if day else ""


def title_for(row: Mapping[str, Any]) -> str:
    """"Submit <the call> by 13 Nov", the call's title cut at a word to fit Linear's 80 characters."""
    day = deadline_day(row.get("due_date"))
    by = f" by {day.day} {MONTHS[day.month - 1]}" if day else ""
    name = " ".join(undash(str(row.get("title") or row["id"])).split())
    room = TITLE_MAX - len("Submit ") - len(by)
    if len(name) > room:
        name = name[: room - 3].rsplit(" ", 1)[0].rstrip(",;:") + "..."
    return f"Submit {name}{by}"


def priority_for(due: datetime | None, now: datetime) -> int:
    """Linear's priority from the deadline: Urgent within 7 days, High within 14, Medium after that or without one."""
    if due is None:
        return 3
    days = (due - now).total_seconds() / 86400
    return 1 if days <= 7 else 2 if days <= 14 else 3


NO_ZONE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2})?$")   # SAM.gov sometimes gives a time without its zone


def _deadline(text: str | None) -> str:
    due = parse_due(text)
    if due is None:
        return str(text or "not given")
    written = str(text).strip()
    if len(written) == 10:   # a bare date
        return day_text(due.date())
    if NO_ZONE.match(written):
        return f"{day_text(due.date())} {written[11:16]} (no time zone given)"
    local = due.astimezone(DASHBOARD_ZONE)
    return f"{day_text(local.date())} {local:%H:%M} {local.tzname()}"


def _extra(row: Mapping[str, Any]) -> dict[str, Any]:
    try:
        found = json.loads(row.get("extra") or "{}")
    except (TypeError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _contact(extra: Mapping[str, Any]) -> str:
    for person in extra.get("samgov_contacts") or extra.get("nasa_contacts") or []:
        if isinstance(person, dict) and str(person.get("name") or "").strip():
            return ", ".join(str(person[k]).strip() for k in ("name", "email") if str(person.get(k) or "").strip())
    return ""


def body_for(row: Mapping[str, Any]) -> str:
    """The issue's description: who pursued it, what the call asks, why it fits, its details and its links."""
    extra = _extra(row)
    why = [f"- Claude, {row.get('ai_verdict') or 'not reviewed'}: {row.get('ai_reasoning') or 'no reason given'}"]
    if row.get("grok_verdict"):
        why.append(f"- Grok, {row['grok_verdict']}: {row.get('grok_reasoning') or 'no reason given'}")
    details = [("Portal", ", ".join(str(row[k]) for k in ("portal", "type") if row.get(k))),
               ("Agency", row.get("department")), ("Deadline", _deadline(row.get("due_date"))),
               ("Set-aside", row.get("set_aside")), ("NAICS", row.get("naics_code")),
               ("Solicitation", extra.get("samgov_solicitation_number")), ("Contact", _contact(extra))]
    links = [f"- [The call on {row.get('portal') or 'its portal'}]({row['url']})"] if row.get("url") else []
    dashboard = (get("DASHBOARD_URL") or "").strip().rstrip("/")
    if dashboard:
        links.append(f"- [The call on the dashboard]({dashboard}/proposals/{urllib.parse.quote(str(row['id']), safe='')})")
    lines = [f"Marked Pursue on the dashboard by {row.get('human_by') or 'someone'}{_on(row.get('human_at'))}.", "",
             "**What the call asks**", str(row.get("ai_summary") or "No summary yet."), "",
             "**Why it fits**", *why, "",
             "**Details**", *[f"- {label}: {' '.join(str(value).split())}" for label, value in details if value], "",
             "**Links**", *links]
    return undash("\n".join(lines).strip())


def email_for(name: str | None) -> str | None:
    """The address of the person who marked Pursue: theirs in DASHBOARD_USERS, else their sign-in (people)."""
    if not name:
        return None
    for entry in (get("DASHBOARD_USERS") or "").split(","):
        named = NAMED.match(entry.partition("=")[0].strip())
        if named and named.group(1).strip() == name:
            return named.group(2)
    return lq.email_of_person(name)


def _withdrawn(row: Mapping[str, Any]) -> str:
    if row.get("pursuit_state") == "closed":
        return "The draft was closed on the dashboard: the call is no longer pursued."
    if row.get("pursuit_state") == "no_go":
        return "The draft stopped at a no-go on the dashboard: the call is no longer pursued."
    now = DECISIONS.get(str(row.get("human_status")), "undecided")
    return f"Pursue withdrawn on the dashboard by {row.get('human_by') or 'someone'}: the call is now {now}."


def _submitted(row: Mapping[str, Any]) -> str:
    who = row.get("submitted_by") or row.get("human_by") or "someone"
    confirmation = f", confirmation {row['confirmation_number']}" if row.get("confirmation_number") else ""
    return f"Marked Submitted on the dashboard by {who}{_on(row.get('submitted_at') or row.get('human_at'))}{confirmation}."


def _result(row: Mapping[str, Any]) -> str:
    debrief = f" Debrief: {row['debrief']}" if row.get("debrief") else ""
    word = RESULTS.get(str(row.get("result")), str(row.get("result")))
    return undash(f"Result recorded by {row.get('result_by') or 'someone'}{_on(row.get('result_at'))}: {word}.{debrief}")


def _advance(board: Board, row: Mapping[str, Any], issue_id: str, identifier: str, synced: str, stage: str) -> list[str]:
    """Move the issue from the stage it last showed to the call's stage now."""
    call_id = str(row["id"])
    if stage == "withdrawn" and synced in ("submitted", "result"):
        lq.set_linear_stage(call_id, stage)   # a Done issue is never moved again (Velocity's Linear rulebook)
        return []
    if stage == "withdrawn":
        if not board.move(issue_id, "Canceled"):
            return [f"{call_id}: {identifier} could not be canceled; trying again next time"]
        board.comment(issue_id, undash(_withdrawn(row)))
        said = "canceled"
    elif synced in STAGES and STAGES.index(stage) < STAGES.index(synced):
        lq.set_linear_stage(call_id, stage)   # the call went back a step; a person decides what the issue shows
        return []
    elif stage == "drafting":
        if not board.move(issue_id, "In Progress"):
            return [f"{call_id}: {identifier} could not move to In Progress; trying again next time"]
        said = "moved to In Progress"
    elif stage == "submitted":
        if not board.move(issue_id, "Done"):
            return [f"{call_id}: {identifier} could not move to Done; trying again next time"]
        board.comment(issue_id, undash(_submitted(row)))
        said = "moved to Done"
    else:   # result
        if synced != "submitted" and not board.move(issue_id, "Done"):
            return [f"{call_id}: {identifier} could not move to Done; trying again next time"]
        board.comment(issue_id, _result(row))
        said = "result recorded"
    lq.set_linear_stage(call_id, stage)
    return [f"{call_id}: {identifier} {said}"]


def sync(board: Board, now: datetime | None = None) -> list[str]:
    """Open an issue for each newly pursued call and move each issue whose call moved on. Returns what changed."""
    now = now or datetime.now(timezone.utc)
    changes: list[str] = []
    for row in lq.pursuit_issue_rows():
        stage, synced = stage_of(row), row.get("synced")
        if row.get("issue_id") is None or synced == "withdrawn":
            due = parse_due(row.get("due_date"))
            if stage not in OPENS_AT or (due is not None and due < now):   # nothing to submit once a call has closed
                continue
            day = deadline_day(row.get("due_date"))
            issue = board.open(title_for(row), body_for(row), day.isoformat() if day else None, priority_for(due, now),
                               email_for(row.get("human_by")))
            if issue is None:
                changes.append(f"{row['id']}: could not open an issue; trying again next time")
                continue
            lq.save_linear_issue(str(row["id"]), issue, "pursued")
            changes.append(f"{row['id']}: opened {issue['identifier']}")
            if stage == "drafting":
                changes += _advance(board, row, issue["id"], issue["identifier"], "pursued", stage)
        elif stage != synced:
            changes += _advance(board, row, str(row["issue_id"]), str(row["identifier"]), str(synced), stage)
    return changes
