"""DoD topics to `calls` rows, from SBIR.gov's topic page or from DSIP's own topic DOCX. Pure: no network, no ledger.

    fields = read_topic_page(html)                          # SBIR.gov's copy of one topic
    rec = from_sbirgov(fields, "https://www.sbir.gov/topics/13073", now)
    fields = read_docx(paragraphs, "topic_DAF27BZ01-DV007_Reusable Illumination System.DOCX")
    rec = from_docx(fields, cycle, now)                     # cycle: the AFWERX or SpaceWERX listing that gives its dates

SBIR.gov's topic page has the title, the funding agency, the topic and solicitation numbers, the program and phase tags,
the status, a release schedule (Release Date, Open Date, Due Date(s), Close Date) and the description. DSIP's DOCX opens
with "TOPIC: Title" and then labelled sections (PROJECTED CMMC LEVEL REQUIREMENT:, KEYWORDS:, OBJECTIVE:, ITAR:,
DESCRIPTION:, PHASE I: ...), with no dates: those come from the cycle that names the topic's release.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

from portals.dsip.topics import Key, call_id, component_name, parse_topic_number

PORTAL = "DSIP"
TOPICS_URL = "https://www.dodsbirsttr.mil/topics-app/"   # DSIP's topic search: linked for people, never fetched
DESCRIPTION_CHARS = 4000
EASTERN = ZoneInfo("America/New_York")
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december")

HIDDEN = re.compile(r"(?is)<(script|style)\b[^>]*>.*?</\1\s*>")
BREAKS = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6]|tr|td|th)>")
TAGS = re.compile(r"<[^>]+>")
TITLE = re.compile(r"(?is)Back to Funding Opportunities Search\s*</a>.*?<h2[^>]*>(.*?)</h2>")
AGENCY = re.compile(r"(?is)<h3[^>]*>\s*Funding Agency\s*</h3>(.*?)</div>")
PARAGRAPH = re.compile(r"(?is)<p[^>]*>(.*?)</p>")
STRONG = re.compile(r"(?is)<strong>\s*(Year|Topic Number|Solicitation Number):\s*</strong>\s*([^<]*)")
TAGGED = re.compile(r"(?is)Tagged as:\s*</p>(.*?)</div>")
STATUS = re.compile(r"(?is)Solicitation Status:\s*<span[^>]*>(.*?)</span>")
SCHEDULE = re.compile(r"(?is)<strong[^>]*>\s*(Release Date|Open Date|Due Date\(s\)|Close Date)\s*</strong>\s*<br\s*/?>\s*([^<]*)")
DESCRIPTION = re.compile(r'(?is)<div class="pre-form-wrapped usa-prose">(.*?)</div>')
DAY = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})")
FIRST_LINE = re.compile(r"^([A-Za-z0-9-]{6,}):\s*(.+)$")
FILE_NAME = re.compile(r"(?i)^topic_([A-Za-z0-9-]{6,})_(.+?)\.docx$")
LABEL = re.compile(r"^[A-Z0-9][A-Z0-9 ()/&,'-]*:$")
BARE_LABELS = {"ADDITIONAL INFORMATION"}   # DSIP writes this one without a colon
BODY = (("OBJECTIVE", "Objective: "), ("DESCRIPTION", ""), ("PHASE I", "Phase I: "), ("PHASE II", "Phase II: "))


@dataclass(frozen=True)
class Cycle:
    """An AFWERX or SpaceWERX SBIR or STTR cycle as stored in the ledger: what DSIP's DOCX topics take their dates from,
    and what the watch checks has topics."""
    portal: str
    title: str
    keys: frozenset[Key]
    pre_release: date | None
    open: date | None
    close: date | None
    closed: bool


def lines_of(markup: Any) -> list[str]:
    """HTML to text lines: one per paragraph, heading or cell, entities decoded, spaces collapsed."""
    text = html.unescape(TAGS.sub(" ", BREAKS.sub("\n", HIDDEN.sub(" ", str(markup or "")))))
    return [" ".join(line.split()) for line in text.splitlines() if line.strip()]


def _text(markup: str) -> str:
    return " ".join(lines_of(markup))


def parse_day(text: str | None) -> date | None:
    """ "November 4, 2026" or "Nov 4, 2026" to a date; None when it is not one."""
    found = DAY.search(text or "")
    if not found:
        return None
    word, day, year = found.groups()
    month = next((n for n, name in enumerate(MONTHS, 1) if name.startswith(word.lower()[:3])), None)
    try:
        return date(int(year), month, int(day)) if month else None
    except ValueError:
        return None


def shown(day: date) -> str:
    """ "4 Nov 2026" """
    return f"{day.day} {MONTHS[day.month - 1][:3].title()} {day.year}"


def read_topic_page(page: str) -> dict[str, Any]:
    """SBIR.gov's topic page to its fields; a field the page lacks comes back empty."""
    title = TITLE.search(page)
    agency = AGENCY.search(page)
    agencies = [_text(p) for p in PARAGRAPH.findall(agency.group(1))] if agency else []
    labelled = {label: " ".join(value.split()) for label, value in STRONG.findall(page)}
    tagged = TAGGED.search(page)
    status = STATUS.search(page)
    schedule = {label: " ".join(value.split()) for label, value in SCHEDULE.findall(page)}
    description = DESCRIPTION.search(page)
    return {
        "title": _text(title.group(1)) if title else "",
        "agency": next((a for a in reversed(agencies) if a and a.upper() not in ("DOW", "DOD")), agencies[0] if agencies else ""),
        "year": labelled.get("Year", ""),
        "topic": labelled.get("Topic Number", ""),
        "solicitation": labelled.get("Solicitation Number", ""),
        "tags": [_text(p) for p in PARAGRAPH.findall(tagged.group(1))] if tagged else [],
        "status": _text(status.group(1)) if status else "",
        "release": schedule.get("Release Date", ""),
        "open": schedule.get("Open Date", ""),
        "due": schedule.get("Due Date(s)", ""),
        "close": schedule.get("Close Date", ""),
        "description": "\n".join(lines_of(description.group(1))) if description else "",
    }


def _passed(close: date | None, now: datetime) -> bool:
    return close is not None and close < now.astimezone(EASTERN).date()


def _from(department: str) -> str:
    return f"the {department}" if department.startswith(("Department", "Office")) else department


def _dates(pre_release: date | None, opens: date | None, close: date | None) -> str:
    parts = [f"{label} {shown(day)}" for label, day in (("Pre-release", pre_release), ("opens", opens), ("closes", close)) if day]
    return (", ".join(parts) + ".") if parts else ""


def _where(topic: str) -> str:
    return (f"The official topic, its questions and answers, and the submission are on DSIP ({TOPICS_URL}, search for "
            f"{topic}).")


def _record(topic: str, title: str, program: str, phase: str | None, department: str, solicitation: str,
            release: int | None, component: str | None, pre_release: date | None, opens: date | None,
            close: date | None, summary: str, body: str, url: str, source: str, closed: bool,
            more: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": call_id(topic),
        "portal": PORTAL,
        "title": f"{topic} {title}".strip(),
        "type": f"{program} {phase}" if phase else f"{program} topic",
        "department": department,
        "naics_code": "",
        "set_aside": "",
        "posted_date": pre_release.isoformat() if pre_release else "",
        "due_date": close.isoformat() if close else "",
        "description": (f"{summary}\n\n{body}" if body else summary)[:DESCRIPTION_CHARS],
        "url": url,
        "source_type": "html",
        "extra": {
            "dsip_topic": topic,
            "dsip_solicitation": solicitation or None,
            "dsip_release": release,
            "dsip_component": component,
            "dsip_program": program,
            "dsip_phase": phase,
            "dsip_pre_release": pre_release.isoformat() if pre_release else None,
            "dsip_open": opens.isoformat() if opens else None,
            "dsip_source": source,
            **more,
            "dsip_closed": closed,
        },
    }


def from_sbirgov(fields: dict[str, Any], url: str, now: datetime) -> dict[str, Any]:
    """One SBIR.gov topic page's fields to a call. A topic numbered the FY27 way names its component, release and phase;
    one numbered the older way takes its agency and program from the page."""
    topic = " ".join(str(fields.get("topic") or "").split()).upper()
    if not topic:
        raise ValueError("the page has no topic number")
    parsed = parse_topic_number(topic)
    tags = [t.upper() for t in fields.get("tags") or []]
    program = parsed.program if parsed else next((t for t in tags if t in ("SBIR", "STTR")), "SBIR/STTR")
    department = component_name(parsed.component) if parsed else (fields.get("agency") or "Department of War")
    solicitation = parsed.solicitation if parsed else str(fields.get("solicitation") or "")
    pre_release, opens = parse_day(fields.get("release")), parse_day(fields.get("open"))
    close = parse_day(fields.get("close")) or parse_day(fields.get("due"))
    where = f"in solicitation {solicitation}" + (f" Release {parsed.release}" if parsed else "")
    summary = " ".join(part for part in (
        f"A DoD {program} {parsed.phase if parsed else ''}".rstrip() + f" topic from {_from(department)}, {where}.",
        _dates(pre_release, opens, close),
        "Read from SBIR.gov's copy of the topic.",
        _where(topic),
    ) if part)
    node = url.rstrip("/").rsplit("/", 1)[-1]
    return _record(topic, str(fields.get("title") or ""), program, parsed.phase if parsed else None, department, solicitation,
                   parsed.release if parsed else None, parsed.component if parsed else None, pre_release, opens, close,
                   summary, str(fields.get("description") or ""), url, "SBIR.gov",
                   str(fields.get("status") or "").lower() == "closed" or _passed(close, now),
                   {"dsip_sbirgov_id": node if node.isdigit() else None, "dsip_itar": None, "dsip_cmmc": None,
                    "dsip_keywords": None})


def _is_label(text: str) -> bool:
    return bool(LABEL.match(text)) or text in BARE_LABELS


def read_docx(paragraphs: list[str], file_name: str) -> dict[str, Any]:
    """DSIP's topic DOCX, as its paragraphs, to the topic number, title and labelled sections."""
    lines = [" ".join(p.split()) for p in paragraphs if p and p.strip()]
    first = FIRST_LINE.match(lines[0]) if lines else None
    named = FILE_NAME.match(file_name)
    if first and parse_topic_number(first.group(1)):
        topic, title = first.group(1).upper(), first.group(2)
    elif named:
        topic, title = named.group(1).upper(), named.group(2)
    else:
        raise ValueError(f"{file_name} does not open with a topic number")
    sections: dict[str, list[str]] = {}
    current = ""
    for line in lines[1:]:
        if _is_label(line):
            current = line.rstrip(":").strip()
            sections.setdefault(current, [])
        elif current:
            sections[current].append(line)
    return {"topic": topic, "title": title, "sections": {k: "\n".join(v) for k, v in sections.items()}}


def _section(fields: dict[str, Any], name: str) -> str | None:
    value = (fields.get("sections") or {}).get(name)
    return value if value and value.upper() not in ("N/A", "NONE") else None


def from_docx(fields: dict[str, Any], cycle: Cycle | None, now: datetime) -> dict[str, Any]:
    """DSIP's own topic file to a call, with its dates from the cycle that names its release."""
    topic = str(fields["topic"])
    parsed = parse_topic_number(topic)
    program = parsed.program if parsed else "SBIR/STTR"
    department = component_name(parsed.component) if parsed else "Department of War"
    solicitation = parsed.solicitation if parsed else ""
    pre_release, opens, close = (cycle.pre_release, cycle.open, cycle.close) if cycle else (None, None, None)
    itar_text = (fields.get("sections") or {}).get("ITAR")
    where = f"in solicitation {solicitation} Release {parsed.release}" if parsed else "in a DoD solicitation"
    dates = (f"{_dates(pre_release, opens, close)[:-1]} (the dates of {cycle.portal}'s {cycle.title})." if cycle and
             _dates(pre_release, opens, close) else "Its close date is on DSIP; no AFWERX or SpaceWERX cycle names its release.")
    summary = " ".join((
        f"A DoD {program} {parsed.phase if parsed else ''}".rstrip() + f" topic from {_from(department)}, {where}.",
        dates,
        "Read from DSIP's own topic file, downloaded by a person.",
        _where(topic),
    ))
    body = "\n\n".join(f"{shown_as}{text}" for label, shown_as in BODY if (text := _section(fields, label)))
    return _record(topic, str(fields.get("title") or ""), program, parsed.phase if parsed else None, department, solicitation,
                   parsed.release if parsed else None, parsed.component if parsed else None, pre_release, opens, close,
                   summary, body, TOPICS_URL, "DSIP DOCX", _passed(close, now),
                   {"dsip_sbirgov_id": None,
                    "dsip_itar": None if itar_text is None else "restricted" in itar_text.lower(),
                    "dsip_cmmc": _section(fields, "PROJECTED CMMC LEVEL REQUIREMENT"),
                    "dsip_keywords": _section(fields, "KEYWORDS")})
