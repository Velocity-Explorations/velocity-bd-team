"""One DIU solicitation (an "area of interest" in DIU's state) to one `calls` row. Pure: no network, no ledger.

    rec = build_record(aoi, now)

DIU gives a close time such as "2026-10-28 23:59:59 US/Eastern Time" and no posted date. The
solicitation text is its area of interest; the eligibility requirements follow it, so the review
sees who may apply (CLASS ACT, for example, needs a top secret facility clearance).
"""
from __future__ import annotations

import html
import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

PORTAL = "DIU"
ID_PREFIX = "diu-"
DEPARTMENT = "Defense Innovation Unit"
PAGE_URL = "https://www.diu.mil/work-with-us/submit-solution/{number}"   # linked for people, never fetched
DESCRIPTION_CHARS = 4000
EASTERN = "America/New_York"
ZONES = {"eastern": EASTERN, "central": "America/Chicago", "mountain": "America/Denver", "pacific": "America/Los_Angeles"}
CLOSE = re.compile(r"(\d{4})-(\d{2})-(\d{2})[ T](\d{1,2}):(\d{2})(?::(\d{2}))?(?:\s*US/(\w+))?", re.I)
BREAKS = re.compile(r"(?i)<br\s*/?>|</(?:p|div|li|h[1-6]|tr)>")
TAGS = re.compile(r"<[^>]+>")


def plain_text(markup: Any) -> str:
    """HTML to text: one line per paragraph or list item, entities decoded, spaces collapsed."""
    text = html.unescape(TAGS.sub(" ", BREAKS.sub("\n", str(markup or "")))).replace("\xa0", " ").replace("​", "")
    return "\n".join(" ".join(line.split()) for line in text.splitlines() if line.strip())


def derive_type(project_type: Any) -> str:
    """DIU's project types: "2371b OT - CSO", "2374a Prize Challenge", "4022 OT - CLASS ACT"."""
    kind = str(project_type or "").lower()
    if "class act" in kind:
        return "Bridge program"
    if "prize" in kind or "challenge" in kind:
        return "Challenge"
    if "cso" in kind:
        return "CSO"
    return "DIU opportunity"


def close_time(aoi: dict[str, Any]) -> datetime | None:
    """The close time with its zone (Eastern unless DIU names another)."""
    m = CLOSE.search(str(aoi.get("u_aoi_close_date_string") or ""))
    if m:
        year, month, day, hour, minute, second, zone = m.groups()
        return datetime(int(year), int(month), int(day), int(hour), int(minute), int(second or 0),
                        tzinfo=ZoneInfo(ZONES.get((zone or "eastern").lower(), EASTERN)))
    date = str(aoi.get("u_aoi_close_date") or "")
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
        return datetime.fromisoformat(date).replace(hour=23, minute=59, second=59, tzinfo=ZoneInfo(EASTERN))
    return None


def build_record(aoi: dict[str, Any], now: datetime) -> dict[str, Any]:
    number = str(aoi.get("number") or "").strip()
    if not number:
        raise ValueError("the solicitation has no number")
    closes = close_time(aoi)
    text = plain_text(aoi.get("u_area_of_interest")) or plain_text(aoi.get("description"))
    eligibility = plain_text(aoi.get("u_eligibility_requirements"))
    if eligibility:
        text = f"{text}\n\nEligibility: {eligibility}" if text else f"Eligibility: {eligibility}"
    return {
        "id": f"{ID_PREFIX}{number}",
        "portal": PORTAL,
        "title": " ".join(str(aoi.get("u_aoi_title") or "").split()) or number,
        "type": derive_type(aoi.get("u_project_type")),
        "department": DEPARTMENT,
        "naics_code": "",
        "set_aside": "",
        "posted_date": "",
        "due_date": closes.isoformat() if closes else "",
        "description": text[:DESCRIPTION_CHARS],
        "url": PAGE_URL.format(number=number),
        "source_type": "scrape",
        "extra": {
            "diu_number": number,
            "diu_project_type": aoi.get("u_project_type") or None,
            "diu_contracting_shop": aoi.get("u_intended_contracting_shop") or None,
            "diu_close": aoi.get("u_aoi_close_date_string") or None,
            "diu_closed": bool(closes and closes < now),
        },
    }
