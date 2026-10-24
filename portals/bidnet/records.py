"""One BidNet Direct bid to one `calls` row. Pure: no network, no ledger.

    rec = build_record(bid, now)

The lists give a title, a state and two dates, "10/23/2026", with no time; the issuing agency,
description and documents are for paying members. A bid counts as closed from the day after its
closing date, in the state's time.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any
from zoneinfo import ZoneInfo

from portals.bidnet.api import us_date

PORTAL = "BidNet Direct"
ID_PREFIX = "bidnet-"
ZONES = {"Colorado": "America/Denver", "Florida": "America/New_York"}
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
LOCKED = "Its issuing agency, description and documents are for registered BidNet members only."
TYPES = (
    (re.compile(r"(?i)\bRFI\b|request for information"), "RFI"),
    (re.compile(r"(?i)\bRFP\b|requests? for proposals?"), "RFP"),
    (re.compile(r"(?i)\bRFQ\b|request for (?:quot|qualification)"), "RFQ"),
    (re.compile(r"(?i)\b(?:ITB|IFB)\b|invitation (?:to|for) bids?"), "Invitation to bid"),
    (re.compile(r"(?i)sole source"), "Sole source"),
)


def derive_type(title: str) -> str:
    return next((name for pattern, name in TYPES if pattern.search(title)), "Solicitation")


def _short(day: Any) -> str:
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def build_record(bid: dict[str, Any], now: datetime) -> dict[str, Any]:
    bid_id = str(bid.get("bid_id") or "").strip()
    state = str(bid.get("state") or "").strip()
    if not bid_id or not state:
        raise ValueError("the bid has no id or state")
    title = " ".join(str(bid.get("title") or "").split()) or f"BidNet bid {bid_id}"
    closing_text = str(bid.get("closing") or "").strip()
    published, closes = us_date(bid.get("published")), us_date(closing_text)
    parts = [f"published {_short(published)}"] if published else []
    if closes:
        parts.append(f"closes {_short(closes)}")
    else:
        parts.append(f"closes {closing_text}" if closing_text else "with no closing date shown")
    dates = ", ".join(parts)
    today = now.astimezone(ZoneInfo(ZONES.get(state, "America/Denver"))).date()
    return {
        "id": f"{ID_PREFIX}{state.lower()}-{bid_id}",
        "portal": PORTAL,
        "title": title,
        "type": derive_type(title),
        "department": f"{state} state and local agencies",
        "naics_code": "",
        "set_aside": "",
        "posted_date": published.isoformat() if published else "",
        "due_date": closes.isoformat() if closes else "",
        "description": (f"A {state} state or local government solicitation listed on BidNet Direct. "
                        f"{dates[:1].upper()}{dates[1:]}. {LOCKED}"),
        "url": str(bid.get("link") or ""),
        "source_type": "scrape",
        "extra": {
            "bidnet_state": state,
            "bidnet_bid_id": bid_id,
            "bidnet_closing": closing_text or None,
            # No closing date on the list: none to read by design. One that cannot be read is
            # not, so the scan quality alert still counts it.
            "bidnet_no_deadline": not closing_text,
            "bidnet_closed": bool(closes and closes < today),
        },
    }
