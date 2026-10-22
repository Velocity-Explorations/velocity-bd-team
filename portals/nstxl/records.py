"""One NSTXL opportunity post to one `calls` row. Pure: no network, no ledger.

    reason = is_open(item, statuses, now)        # None, or why the item is not open
    rec = build_record(item, statuses, otas, now)

Posts have no deadline field. Their text lists updates newest first ("RFS REVISION 1: Posted
on 20 October 2026. The Government extended the solution deadline to 30 October 2026 ..."), so
the deadline is the first date the text introduces with a deadline word, skipping "posted"
dates. A post whose public text gives none (coming soon, member-only, or the deadline is only in
its documents) says so in `extra`.
"""
from __future__ import annotations

import html
import re
from datetime import date, datetime, timedelta, timezone
from typing import Any

PORTAL = "NSTXL"
ID_PREFIX = "nstxl-"
DESCRIPTION_CHARS = 3000
MEMBERS_MARK = "member only page"
MEMBERS_NOTE = "Member-only page on NSTXL: sign in as a member to read it."
STALE_AFTER = timedelta(days=365)
HEAD_CHARS = 600          # the newest updates, where a cancellation or award is announced
LOOKBACK = 100

OPEN_STATUS = re.compile(r"\bcurrent\b|coming soon", re.I)
SHUT_STATUS = re.compile(r"closed|archived|under eval|awarded", re.I)
SHUT_TEXT = ("has been canceled", "has been cancelled", "has been awarded", "award notice", "now closed",
             "no longer available")
CONSORTIA = {"s2marts": "S2MARTS", "spec": "SpEC", "jdec": "JDEC", "mec": "Microelectronics Commons",
             "commons": "Microelectronics Commons", "microelectronics commons": "Microelectronics Commons",
             "trex": "TReX"}

MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
MONTH = r"(jan(?:uary)?|feb(?:ruary)?|mar(?:ch)?|apr(?:il)?|may|june?|july?|aug(?:ust)?|sep(?:t(?:ember)?)?|oct(?:ober)?|nov(?:ember)?|dec(?:ember)?)"
DAY_FIRST = re.compile(rf"\b(\d{{1,2}})\s+{MONTH}\.?(?:,?\s+(\d{{4}}))?\b", re.I)
MONTH_FIRST = re.compile(rf"\b{MONTH}\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b", re.I)
DEADLINE_WORD = re.compile(r"\b(due|deadline|until|no later than|close[sd]?|submit\w*|extend\w*|by)\b", re.I)
POSTED = re.compile(r"\b(posted|updated|released|revised|issued)(\s+on)?\s*:?\s*$", re.I)
BREAKS = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6]|tr)>")
TAGS = re.compile(r"<[^>]+>")


def plain_text(markup: str) -> str:
    """HTML to text: one line per paragraph or list item, entities decoded, spaces collapsed."""
    text = html.unescape(TAGS.sub(" ", BREAKS.sub("\n", markup or ""))).replace("\xa0", " ").replace("​", "")
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def _title(item: dict[str, Any]) -> str:
    return " ".join(html.unescape(str((item.get("title") or {}).get("rendered") or "")).split())


def _status_names(item: dict[str, Any], statuses: dict[int, str]) -> list[str]:
    return [statuses.get(int(s), "") for s in item.get("opp_status") or [] if statuses.get(int(s))]


def _modified(item: dict[str, Any]) -> datetime:
    moment = datetime.fromisoformat(str(item.get("modified") or item.get("date")))
    return moment if moment.tzinfo else moment.replace(tzinfo=timezone.utc)


def is_open(item: dict[str, Any], statuses: dict[int, str], now: datetime) -> str | None:
    """Why this post is not an open opportunity, or None when it is."""
    if _title(item).lower() == "access test":
        return "test page"
    names = _status_names(item, statuses)
    shut = next((n for n in names if SHUT_STATUS.search(n)), None)
    if shut:
        return f"status {shut}"
    if not any(OPEN_STATUS.search(n) for n in names):
        return "no open status"
    head = plain_text(str((item.get("content") or {}).get("rendered") or ""))[:HEAD_CHARS].lower()
    phrase = next((p for p in SHUT_TEXT if p in head), None)
    if phrase:
        return f"text says '{phrase}'"
    modified = _modified(item)
    if now - modified > STALE_AFTER:
        return f"not updated since {modified.date().isoformat()}"
    return None


def _dates(text: str) -> list[tuple[int, int, int, int, int | None]]:
    """(start, end, day, month, year or None) for every date in the text, in order."""
    found = []
    for m in DAY_FIRST.finditer(text):
        found.append((m.start(), m.end(), int(m.group(1)), MONTHS.index(m.group(2)[:3].lower()) + 1,
                      int(m.group(3)) if m.group(3) else None))
    for m in MONTH_FIRST.finditer(text):
        found.append((m.start(), m.end(), int(m.group(2)), MONTHS.index(m.group(1)[:3].lower()) + 1,
                      int(m.group(3)) if m.group(3) else None))
    found.sort()
    kept: list[tuple[int, int, int, int, int | None]] = []
    for entry in found:
        if not kept or entry[0] >= kept[-1][1]:
            kept.append(entry)
    return kept


def _sentence(text: str, start: int, end: int) -> str:
    """The sentence around text[start:end], for showing where a deadline came from."""
    begin = 0
    for m in re.finditer(r"[.!?]\s+|\n", text[:start]):
        begin = m.end()
    after = re.search(r"[.!?](?=\s|$)|\n", text[end:])
    if after is None:
        stop = len(text)
    elif after.group() == "\n":
        stop = end + after.start()
    else:
        stop = end + after.end()
    return text[begin:stop].strip()[:300]


def deadline(text: str, posted: date) -> tuple[str, str] | None:
    """The newest deadline in the text as (YYYY-MM-DD, its sentence), or None. A date without a year
    takes the first year that puts it on or after the post's date."""
    previous_end = 0
    for start, end, day, month, year in _dates(text):
        before = text[max(previous_end, start - LOOKBACK):start]
        previous_end = end
        if POSTED.search(before) or not DEADLINE_WORD.search(before):
            continue
        try:
            due = date(year or posted.year, month, day)
            if year is None and due < posted:
                due = date(posted.year + 1, month, day)
        except ValueError:
            continue
        return due.isoformat(), _sentence(text, start, end)
    return None


def derive_type(title: str, text: str, statuses: list[str]) -> str:
    head = f"{title} {text[:300]}".lower()
    names = " ".join(statuses).lower()
    if "industry day" in head:
        return "Industry day"
    if "white paper" in head:   # what a coming-soon notice asks for, when it asks for one
        return "White paper"
    if re.search(r"\brf[in]\b|request for (information|network insight)", head):
        return "RFI"
    if "call for projects" in head or "call for projects" in names:
        return "Call for projects"
    if "coming soon" in names or "coming soon" in text[:300].lower():
        return "Coming soon"
    if re.search(r"\b(d?rfs|d?rpp|rfp)\b|request for (prototype )?(proposals|solutions)|solution papers?", head):
        return "Solicitation"
    return "OTA opportunity"


def consortium(item: dict[str, Any], statuses: dict[int, str], otas: dict[int, str]) -> str:
    """S2MARTS, SpEC, JDEC, Microelectronics Commons or TReX: the OTA term, else the status name's prefix."""
    for ota in item.get("ota") or []:
        known = CONSORTIA.get(otas.get(int(ota), "").strip().lower())
        if known:
            return known
    for name in _status_names(item, statuses):
        first = re.split(r"[\s-]+", name.strip().lower(), maxsplit=1)[0]
        if first in CONSORTIA:
            return CONSORTIA[first]
    return PORTAL


def build_record(item: dict[str, Any], statuses: dict[int, str], otas: dict[int, str], now: datetime) -> dict[str, Any]:
    text = plain_text(str((item.get("content") or {}).get("rendered") or ""))
    members_only = MEMBERS_MARK in text.lower()
    names = _status_names(item, statuses)
    posted = date.fromisoformat(str(item["date"])[:10])
    found = None if members_only else deadline(text, posted)
    due = found[0] if found else ""
    closed =is_open(item, statuses, now) is not None or bool(due and date.fromisoformat(due) < now.date())
    group = consortium(item, statuses, otas)
    title = _title(item)
    extra = {
        "nstxl_post_id": item["id"],
        "nstxl_consortium": group,
        "nstxl_statuses": names or None,
        "nstxl_modified": item.get("modified"),
        "nstxl_deadline_text": found[1] if found else None,
        "nstxl_members_only": members_only,
        # Many posts keep the deadline in the attached RPP or RFS, coming-soon notices have none yet,
        # and member-only text cannot be read: none of that is a page read badly.
        "nstxl_no_deadline": not due,
        "nstxl_closed": closed,
    }
    return {
        "id": f"{ID_PREFIX}{item['id']}",
        "portal": PORTAL,
        "title": title or "(untitled opportunity)",
        "type": derive_type(title, text, names),
        "department": group,
        "naics_code": "",
        "set_aside": "",
        "posted_date": posted.isoformat(),
        "due_date": due,
        "description": MEMBERS_NOTE if members_only else text[:DESCRIPTION_CHARS],
        "url": item.get("link") or "",
        "source_type": "api",
        "extra": extra,
    }
