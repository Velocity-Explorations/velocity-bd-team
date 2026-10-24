"""One Space Florida RFP to one `calls` row. Pure: no network, no ledger.

    rec = build_record(listing, now)

The page writes dates as "October 7, 2026", without a time. An RFP counts as closed from the day
after its due date in Florida (Eastern) time, or as soon as a Notice of Intent to Award is among
its documents.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

PORTAL = "Space Florida"
ID_PREFIX = "spacefl-"
PAGE_URL = "https://www.spaceflorida.gov/solicitations"
DESCRIPTION_CHARS = 4000
EASTERN = ZoneInfo("America/New_York")
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december")
LONG_DATE = re.compile(r"([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})")
INTENT_TO_AWARD = re.compile(r"(?i)intent to (?:award|enter)")   # "Notice of Intent to Enter Into Negotiations", typos and all
TYPES = (
    (re.compile(r"(?i)\bRFI\b|request for information"), "RFI"),
    (re.compile(r"(?i)\bRFP\b|requests? for proposals?"), "RFP"),
    (re.compile(r"(?i)\bRFQ\b|request for (?:qualification|quot)"), "RFQ"),
    (re.compile(r"(?i)\bRFB\b|request for bids?|invitation (?:to|for) bids?"), "RFB"),
    (re.compile(r"(?i)\bITN\b|invitation to negotiate"), "ITN"),
)


def parse_date(text: Any) -> date | None:
    found = LONG_DATE.search(str(text or ""))
    if not found:
        return None
    word, day, year = found.groups()
    month = next((n for n, name in enumerate(MONTHS, 1) if name.startswith(word.lower())), None)
    if month is None:
        return None
    try:
        return date(int(year), month, int(day))
    except ValueError:
        return None


def derive_type(title: str) -> str:
    return next((name for pattern, name in TYPES if pattern.search(title)), "Solicitation")


def _short(day: date) -> str:
    return f"{day.day} {MONTHS[day.month - 1][:3].title()} {day.year}"


def build_record(listing: dict[str, Any], now: datetime) -> dict[str, Any]:
    title = " ".join(str(listing.get("title") or "").split())
    if not title:
        raise ValueError("the RFP has no title")
    documents = [d for d in listing.get("documents") or [] if isinstance(d, dict) and d.get("name")]
    notes = " ".join(str(listing.get("notes") or "").split())
    published, due = parse_date(listing.get("published")), parse_date(listing.get("due"))
    intent = any(INTENT_TO_AWARD.search(str(d["name"])) for d in documents)
    dates = ", ".join(part for part in (f"published {_short(published)}" if published else "",
                                        f"due {_short(due)}" if due else "") if part)
    first = "A Space Florida solicitation (Florida's aerospace finance and development authority)."
    if dates:
        first += f" {dates[:1].upper()}{dates[1:]}."
    if notes:
        first += f" {notes}"
    description = first
    if documents:
        description += "\n\nDocuments: " + "; ".join(str(d["name"]) for d in documents) + "."
    return {
        "id": ID_PREFIX + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:100],
        "portal": PORTAL,
        "title": title,
        "type": derive_type(title),
        "department": "Space Florida",
        "naics_code": "",
        "set_aside": "",
        "posted_date": published.isoformat() if published else "",
        "due_date": due.isoformat() if due else "",
        "description": description[:DESCRIPTION_CHARS],
        "url": PAGE_URL,
        "source_type": "scrape",
        "extra": {
            "spacefl_documents": [str(d["name"]) for d in documents] or None,   # the page field the assistant lists
            "spacefl_document_links": documents or None,
            "spacefl_notes": notes or None,
            "spacefl_intent_to_award": intent,
            # The page shows no due date: none to read by design. One that cannot be read is not,
            # so the scan quality alert still counts it.
            "spacefl_no_deadline": not str(listing.get("due") or "").strip(),
            "spacefl_closed": intent or bool(due and due < now.astimezone(EASTERN).date()),
        },
    }
