"""One DOE Application Hub item to one `calls` row. Pure: no network, no ledger.

    rec = build_record(item, now)

An item's text starts with its title, its category, "Submission Deadline: September 10, 2026 at
2 PM ET" and a contact line, then Information, Topics, Process Details, How to Apply and a table
of files. The description is a summary line, then the Information and Topics; the deadline is
read in Eastern time, or as a bare date from the excerpt ("Submission Deadline: 09/10/2026").
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

PORTAL = "DOE SBIR"
ID_PREFIX = "doe-"
DEPARTMENT = "DOE Office of Technology Commercialization"
HUB = "DOE's SBIR/STTR Application Hub"
HUB_URL = "https://sbir-sttr.connectwerx.org/opportunities/"
DESCRIPTION_CHARS = 4000
EASTERN = ZoneInfo("America/New_York")
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december")
STOPS = ("process details", "how to participate", "how to apply", "timeline", "future considerations", "file title")
SUMMARY = {"Active": "An active", "Upcoming": "An upcoming", "Closed": "A closed", "": "A"}

HIDDEN = re.compile(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>")
BREAKS = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6]|tr|td|th)>")
TAGS = re.compile(r"<[^>]+>")
STATUS = re.compile(r"^portfolio_category-(active|upcoming|closed)-solicitation$")
DEADLINE = re.compile(r"(?i)submission deadline\s*:\s*([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})"
                      r"(?:\s+at\s+(\d{1,2})(?::(\d{2}))?\s*([ap])\.?\s*m\b\.?)?")
SHORT_DEADLINE = re.compile(r"(?i)submission deadline\s*:\s*(\d{1,2})/(\d{1,2})/(\d{4})")
NOT_SET = re.compile(r"(?i)\b(?:tbd|tba|to be (?:announced|determined)|rolling|continuous)\b")
PHASE = re.compile(r"(?i)\bphase\s+(ii|i)\b")


def lines_of(markup: Any) -> list[str]:
    """HTML to text lines: one per paragraph, heading or cell, entities decoded, spaces collapsed."""
    text = html.unescape(TAGS.sub(" ", BREAKS.sub("\n", HIDDEN.sub(" ", str(markup or "")))))
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _rendered(item: dict[str, Any], key: str) -> str:
    value = item.get(key)
    return str(value.get("rendered") or "") if isinstance(value, dict) else str(value or "")


def status_of(item: dict[str, Any]) -> str:
    """Active, Upcoming or Closed, from the item's category class; empty when it has none."""
    for name in item.get("class_list") or []:
        found = STATUS.match(str(name))
        if found:
            return found.group(1).title()
    return ""


def deadline(item: dict[str, Any]) -> tuple[datetime | date | None, str]:
    """The submission deadline and the words it was read from. A time comes with its date in the
    text; the excerpt gives the date alone."""
    seen = ""
    for line in lines_of(_rendered(item, "content")):
        if "submission deadline" not in line.lower():
            continue
        seen = line
        found = DEADLINE.search(line)
        if found:
            word, day, year, hour, minute, half = found.groups()
            month = next((n for n, name in enumerate(MONTHS, 1) if name.startswith(word.lower())), None)
            if month is not None:
                try:
                    if hour is None:
                        return date(int(year), month, int(day)), line
                    clock = int(hour) % 12 + (12 if half.lower() == "p" else 0)
                    return datetime(int(year), month, int(day), clock, int(minute or 0), tzinfo=EASTERN), line
                except ValueError:
                    pass
        break
    short = SHORT_DEADLINE.search(" ".join(lines_of(_rendered(item, "excerpt"))))
    if short:
        month, day, year = (int(part) for part in short.groups())
        try:
            return date(year, month, day), short.group(0)
        except ValueError:
            pass
    return None, seen


def _shown(due: datetime | date) -> str:
    """ "3 Dec 2026 at 5 PM ET", or "3 Dec 2026" for a bare date."""
    day = f"{due.day} {MONTHS[due.month - 1][:3].title()} {due.year}"
    if not isinstance(due, datetime):
        return day
    clock = f"{due.hour % 12 or 12}" + (f":{due.minute:02d}" if due.minute else "")
    return f"{day} at {clock} {'AM' if due.hour < 12 else 'PM'} ET"


def body_text(lines: list[str]) -> str:
    """The Information section and the topics: from "Information" up to the process, timeline and files."""
    lowered = [line.lower() for line in lines]
    start = next((i + 1 for i, line in enumerate(lowered) if line == "information"), None)
    if start is None:
        start = next((i + 1 for i, line in enumerate(lowered) if line.startswith("questions?")), 0)
    kept: list[str] = []
    for line in lines[start:]:
        if line.lower().rstrip(":").strip() in STOPS:
            break
        kept.append(line)
    return "\n".join(kept)


def derive_type(title: str) -> str:
    found = PHASE.search(title)
    return f"SBIR/STTR Phase {found.group(1).upper()}" if found else "SBIR/STTR solicitation"


def build_record(item: dict[str, Any], now: datetime) -> dict[str, Any]:
    post_id = item.get("id")
    if not post_id:
        raise ValueError("the item has no id")
    title = " ".join(html.unescape(_rendered(item, "title")).split()) or f"DOE solicitation {post_id}"
    status = status_of(item)
    due, deadline_text = deadline(item)
    no_deadline = due is None and (status == "Upcoming" or bool(NOT_SET.search(deadline_text)))
    if isinstance(due, datetime):
        passed = due < now
    else:
        passed = due is not None and due < now.astimezone(EASTERN).date()
    summary = f"{SUMMARY[status]} DOE SBIR/STTR solicitation on {HUB}."
    if due is not None:
        summary += f" Submission deadline: {_shown(due)}."
    elif no_deadline:
        summary += " No submission deadline yet."
    else:
        summary += " Its deadline could not be read; see its page."
    body = body_text(lines_of(_rendered(item, "content")))
    return {
        "id": f"{ID_PREFIX}{post_id}",
        "portal": PORTAL,
        "title": title,
        "type": derive_type(title),
        "department": DEPARTMENT,
        "naics_code": "",
        "set_aside": "",
        "posted_date": str(item.get("date") or "")[:10],
        "due_date": due.isoformat() if due is not None else "",
        "description": (f"{summary}\n\n{body}" if body else summary)[:DESCRIPTION_CHARS],
        "url": str(item.get("link") or HUB_URL),
        "source_type": "api",
        "extra": {
            "doe_post_id": post_id,
            "doe_status": status or None,
            "doe_modified": item.get("modified") or None,
            "doe_deadline_text": deadline_text or None,
            # Upcoming with no date yet, TBD or rolling: no deadline by design. A deadline that
            # cannot be read is not, so the scan quality alert still counts it.
            "doe_no_deadline": no_deadline,
            "doe_closed": status == "Closed" or passed,
        },
    }
