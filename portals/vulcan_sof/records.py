"""One Vulcan SOF call, as its call feed gives it, to one `calls` row. Pure: no network, no ledger.

    rec = build_record(feed, url, now)

Vulcan redesigned its call pages on or before 16 Nov 2026: the page text no longer shows the deadline's time, and its
sections were renamed. The page itself loads the call from Vulcan's call feed (`/apiv1/call/get?uuid=<uuid>`, read
through the logged-in session in scrape.py), which carries exact UTC times, the objectives, documents, instructions and
tags. The record keeps the columns and `extra` keys the page-text reader wrote, so a call updates in place.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

PORTAL = "Vulcan SOF"
DEPARTMENT = "USSOCOM / SOF Enterprise"
DEFAULT_TYPE = "Open Call"
ID_PREFIX = "vulcan-"
# Vulcan's pages showed dates in the account's own zone, Mountain time, as "21 OCT 2026 : 21:59 MDT"; the ledger's Vulcan
# rows and every due_date reader expect that form.
SHOWN_ZONE = ZoneInfo("America/Denver")
DESC_MIN_CHARS = 40
DESC_MAX_CHARS = 1500
INSTRUCTIONS_MAX_CHARS = 1200
# The feed's objective codes, as Vulcan's own filter names them (and as review/tags.py TYPE_BY_KIND reads them).
OBJECTIVES = {
    "OTA_PROTOTYPE": "OTA Prototype",
    "FAR_ACQUISITION": "FAR Acquisition",
    "FAR_AQUISITION": "FAR Acquisition",   # as Vulcan's feed spells it
    "TECH_EXPERIMENTATION": "Tech Experimentation",
    "CAPABILITY_DEMONSTRATION": "Capability Demonstration",
    "SBIR_STTR": "SBIR / STTR",
    "CRADA": "CRADA",
    "PRIZE_CHALLENGE": "Prize Challenge",
    "MARKET_RESEARCH": "Market Research",
}


# Which objective names a call with several: the most binding vehicle first. The feed lists them alphabetically, so the
# order the page used to show is gone; a call already in the ledger keeps its type while it is still one of them.
BINDING = ["FAR Acquisition", "OTA Prototype", "SBIR / STTR", "Prize Challenge", "CRADA", "Capability Demonstration",
           "Tech Experimentation", "Market Research"]


def objective_name(code: str) -> str:
    """An objective code as Vulcan names it; an unknown code in plain words."""
    return OBJECTIVES.get(code) or " ".join(word.capitalize() for word in str(code).split("_") if word)


def _text(value: Any) -> str:
    return " ".join(str(value or "").split())


def _when(value: Any) -> datetime | None:
    """A feed time ("2026-10-22T03:59:00.000Z") as an aware datetime, or None."""
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def _shown(moment: datetime | None, month_upper: bool) -> str:
    """A time as Vulcan's pages showed it: "21 OCT 2026 : 21:59 MDT" for a deadline, "13 Oct 2026 : 22:00 MDT" for an
    open date."""
    if moment is None:
        return ""
    local = moment.astimezone(SHOWN_ZONE)
    month = local.strftime("%b").upper() if month_upper else local.strftime("%b")
    return f"{local:%d} {month} {local:%Y} : {local:%H:%M} {local.tzname()}"


def _names(items: Any, *keys: str) -> list[str]:
    """Each item's first non-empty name among `keys`; a plain string as it is."""
    found: list[str] = []
    for item in items or []:
        if isinstance(item, str):
            name = _text(item)
        elif isinstance(item, dict):
            name = next((_text(item.get(k)) for k in keys if _text(item.get(k))), "")
        else:
            name = ""
        if name:
            found.append(name)
    return found


def call_type(objectives: list[str], known_type: str | None = None) -> str:
    """The call's type: the one it already has while that is still among its objectives, else the most binding."""
    if known_type and known_type in objectives:
        return known_type
    ranked = sorted(objectives, key=lambda name: BINDING.index(name) if name in BINDING else len(BINDING))
    return ranked[0] if ranked else DEFAULT_TYPE


def build_record(feed: dict[str, Any], url: str, now: datetime, known_type: str | None = None) -> dict[str, Any]:
    """The `calls` row for one call feed item. `url` is the call's link on the listing; `now` decides closed;
    `known_type` is the type the ledger already holds for the call, if any."""
    objectives = list(dict.fromkeys(objective_name(code) for code in feed.get("engagementObjectives") or []))
    description = _text(feed.get("description"))[:DESC_MAX_CHARS]
    deadline = _when(feed.get("submissionEnd"))
    return {
        "id": f"{ID_PREFIX}{feed['uuid']}",
        "title": _text(feed.get("name")),
        "portal": PORTAL,
        "type": call_type(objectives, known_type),
        "department": DEPARTMENT,
        "naics_code": "",
        "set_aside": "",
        "posted_date": _shown(_when(feed.get("submissionStart")), month_upper=False),
        "due_date": _shown(deadline, month_upper=True),
        "description": description,
        "url": url,
        "source_type": "regular",
        "extra": {
            "vulcan_description_fallback": len(description) < DESC_MIN_CHARS,
            "vulcan_closed": bool(deadline and deadline <= now),
            "vulcan_objectives": objectives,
            "vulcan_documents": _names(feed.get("documents"), "description", "filename"),
            "vulcan_files_required": _names(feed.get("customRequirements"), "name", "title", "description"),
            "vulcan_tags": _names(feed.get("tags"), "name", "label"),
            "vulcan_instructions": _text(feed.get("instruction"))[:INSTRUCTIONS_MAX_CHARS],
        },
    }
