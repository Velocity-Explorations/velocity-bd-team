"""Deadlines as portals write them, for the workspace's dates (PRO-577).

    parse_due("30 OCT 2026 : 21:59 MDT")   -> 2026-10-31 03:59 UTC
    deadline_day("30 OCT 2026 : 21:59 MDT") -> 2026-10-30, the day in Denver, as the dashboard shows it
    business_day_before(date(2026, 11, 2))  -> 2026-10-30, the internal submit-by date (PW9)

parse_due mirrors assistant/dates.py, which the 08:00 reminder uses: components share no code
(AGENTS.md, hard rule 1), so a change to one belongs in the other. Anything unreadable comes
back as None, and the caller leaves the date unset.
"""
from __future__ import annotations

import re
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc
DASHBOARD_ZONE = ZoneInfo("America/Denver")
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}
ZONES = {
    "UTC": 0, "GMT": 0, "Z": 0,
    "EST": -5, "EDT": -4, "CST": -6, "CDT": -5, "MST": -7, "MDT": -6,
    "PST": -8, "PDT": -7, "AKST": -9, "AKDT": -8, "HST": -10,
    "BST": 1, "CET": 1, "CEST": 2,
}
PORTAL_FORMAT = re.compile(
    r"^(\d{1,2})\s+([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{4})(?:\s*:?\s*(\d{1,2}):(\d{2}))?\s*([A-Za-z]{1,5})?$"
)


def parse_due(text: str | None) -> datetime | None:
    """A deadline as a UTC datetime; a bare date means the end of that day."""
    if not text or not text.strip():
        return None
    value = text.strip()
    match = PORTAL_FORMAT.match(value)
    if match:
        day, month_word, year, hour, minute, zone = match.groups()
        month = MONTHS.get(month_word.upper())
        if month is None:
            return None
        offset = timezone(timedelta(hours=ZONES.get((zone or "UTC").upper(), 0)))
        try:
            local = datetime(int(year), month, int(day),
                             int(hour) if hour else 23, int(minute) if minute else 59, tzinfo=offset)
        except ValueError:
            return None
        return local.astimezone(UTC)
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if len(value) == 10:   # a bare YYYY-MM-DD
        parsed = parsed.replace(hour=23, minute=59)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def deadline_day(text: str | None) -> date | None:
    """The deadline's day in Denver, the dashboard's zone; a bare date stays that date."""
    value = (text or "").strip()
    if len(value) == 10:
        try:
            return date.fromisoformat(value)
        except ValueError:
            return None
    due = parse_due(value)
    return due.astimezone(DASHBOARD_ZONE).date() if due else None


def business_day_before(day: date) -> date:
    """The weekday before a date: Monday's is the Friday before."""
    before = day - timedelta(days=1)
    while before.weekday() >= 5:
        before -= timedelta(days=1)
    return before
