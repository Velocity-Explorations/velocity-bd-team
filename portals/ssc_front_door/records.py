"""One Front Door listing to one `calls` row. Pure: no network, no ledger.

    rec = build_record(listing, now)   # dict matching the ledger's calls columns

Listings carry no notice type, NAICS code, set-aside or office, so `type` is read from the
title (RFI, CSO, industry day, webinar and so on) and `department` from the one field that
sometimes names SSC offices. Dates are UTC with the event's own time zone beside them.
"""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from portals.ssc_front_door.api import BASE

PORTAL = "SSC Front Door"
ID_PREFIX = "sscfd-"
SSC = "Space Systems Command"
DESCRIPTION_CHARS = 1500
MONTHS = ("JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC")

SAM_RE = re.compile(r"sam\.gov/(?:workspace/contract/)?opp/([0-9a-f]{32})", re.I)
TAG_RE = re.compile(r"<[^>]+>")
# Title patterns in order; the first that matches names the type. Solicitation types come first,
# so "Industry Day and RFI" is judged as an RFI, not as an event.
TYPES = [
    ("RFI", re.compile(r"\bRFI\b|request for information", re.I)),
    ("Sources sought", re.compile(r"sources? sought", re.I)),
    ("CSO", re.compile(r"\bCSO\b|commercial solutions? opening", re.I)),
    ("Solicitation", re.compile(r"\bBAA\b|\bRFP\b|broad agency announcement|solicitation", re.I)),
    ("Industry day", re.compile(r"industry days?\b", re.I)),
    ("Webinar", re.compile(r"webinar", re.I)),
    ("Challenge", re.compile(r"challenge|prize", re.I)),
    ("Conference", re.compile(r"conference|symposium|summit|forum|expo\b|convention", re.I)),
]
SAM_FALLBACK_TYPES = ("RFI", "Sources sought", "CSO", "Solicitation")


def node(listing: dict[str, Any], name: str) -> Any:
    """A content node's value (text) or the node itself (dates), or None."""
    value = (listing.get("contentNodes") or {}).get(name)
    if isinstance(value, dict) and "value" in value:
        return value["value"]
    return value


def clean(text: str | None) -> str:
    """HTML entities decoded, tags dropped, zero-width and non-breaking spaces gone, whitespace collapsed."""
    value = TAG_RE.sub(" ", html.unescape(text or ""))
    return " ".join(value.replace("​", "").replace("\xa0", " ").split())


def derive_type(title: str, location: str = "", description: str = "") -> str:
    """The listing's type from its title, or "Webinar" from its location; reposted SAM.gov
    notices without one in the title are read from the description."""
    for name, pattern in TYPES:
        if pattern.search(title) or (name == "Webinar" and pattern.search(location)):
            return name
    if location.strip().upper() == "SAM.GOV":
        for name, pattern in TYPES:
            if name in SAM_FALLBACK_TYPES and pattern.search(description):
                return name
        return "SAM.gov notice"
    return "Event"


def _instant(value: Any) -> datetime | None:
    raw = value.get("dateTimeValue") if isinstance(value, dict) else None
    if not raw:
        return None
    return datetime.fromisoformat(raw.replace("Z", "+00:00")).astimezone(timezone.utc)


def _iso(moment: datetime | None) -> str | None:
    return moment.strftime("%Y-%m-%dT%H:%M:%SZ") if moment else None


def _zone(value: Any) -> ZoneInfo:
    name = value.get("timeZone") if isinstance(value, dict) else None
    try:
        return ZoneInfo(name) if name else ZoneInfo("UTC")
    except (ZoneInfoNotFoundError, ValueError):
        return ZoneInfo("UTC")


def local_deadline(moment: datetime | None, zone: ZoneInfo) -> str:
    """'11 SEP 2026 : 15:00 PDT': the portal format assistant/dates.py reads, in the event's own zone."""
    if moment is None:
        return ""
    local = moment.astimezone(zone)
    return f"{local.day:02d} {MONTHS[local.month - 1]} {local.year} : {local:%H:%M} {local.tzname() or 'UTC'}"


def sam_notice_id(listing: dict[str, Any]) -> str | None:
    for name in ("eventURL", "eventRegistrationDetails", "eventDescription", "Summary"):
        match = SAM_RE.search(str(node(listing, name) or ""))
        if match:
            return match.group(1).lower()
    return None


def build_record(listing: dict[str, Any], now: datetime) -> dict[str, Any]:
    key = listing["contentKey"]
    title = clean(node(listing, "Title") or listing.get("title"))
    location = clean(node(listing, "eventLocation"))
    description = clean(node(listing, "eventDescription"))
    summary = clean(node(listing, "Summary"))
    audience = clean(node(listing, "eventAudience"))
    if summary and summary != audience and summary not in description:
        description = f"{summary} {description}".strip()
    start, end = node(listing, "eventStartDate"), node(listing, "eventEndDate")
    ends = _instant(end)
    sam_id = sam_notice_id(listing)
    offices = clean(node(listing, "governmentOrganizations"))
    published = _instant({"dateTimeValue": listing.get("publishedDate")})
    return {
        "id": f"{ID_PREFIX}{key}",
        "title": title,
        "portal": PORTAL,
        "type": derive_type(title, location, description),
        "department": offices or (SSC if sam_id else ""),
        "naics_code": "",
        "set_aside": "",
        "posted_date": published.strftime("%Y-%m-%d") if published else "",
        "due_date": local_deadline(ends, _zone(end)),
        "description": description[:DESCRIPTION_CHARS],
        "url": f"{BASE}/s/events/{listing.get('contentUrlName', '')}-{key}",
        "source_type": "scrape",
        "extra": {
            "sscfd_content_key": key,
            "sscfd_start": _iso(_instant(start)),
            "sscfd_end": _iso(ends),
            "sscfd_time_zone": end.get("timeZone") if isinstance(end, dict) else None,
            "sscfd_location": location or None,
            "sscfd_event_url": node(listing, "eventURL") or None,
            "sscfd_registration": clean(node(listing, "eventRegistrationDetails")) or None,
            "sscfd_audience": audience or None,
            "sscfd_sam_notice_id": sam_id,
            "sscfd_sam_url": f"https://sam.gov/opp/{sam_id}/view" if sam_id else None,
            "sscfd_closed": bool(ends and ends < now),
        },
    }
