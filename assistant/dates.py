"""Deadlines as portals write them, turned into UTC datetimes.

    parse_due("30 OCT 2026 : 21:59 MDT")  -> 2026-10-31 03:59 UTC
    parse_due("2026-11-01")               -> 2026-11-01 23:59 UTC (a bare date means end of day)

calls.due_date holds the portal's own text, so anything unreadable comes back as None and the
caller simply leaves that call out of date-based lists.
"""
from __future__ import annotations

import math
import re
from datetime import datetime, timedelta, timezone

UTC = timezone.utc
MONTHS = {m: i for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"], start=1)}
# Zone abbreviations portals use, as hours from UTC: US zones, plus the UK and central Europe for
# SSC Front Door events held there. Anything else is read as UTC.
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


def days_until(due: datetime, now: datetime | None = None) -> int:
    """Whole days left, rounded down; negative once the deadline has passed."""
    now = now or datetime.now(UTC)
    return math.floor((due - now).total_seconds() / 86400)
