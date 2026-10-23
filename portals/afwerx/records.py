"""One AFWERX cycle to one `calls` row. Pure: no network, no ledger.

    rec = build_record(cycle, now)

AFWERX writes dates as "7 Oct 26" or "13 APRIL 26", with no time of day. The close date is the
deadline, and a cycle counts as closed from the next day in Eastern time. AFWERX lists the
cycle, not its topics, so the description says what the cycle is and where its topics are.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

PORTAL = "AFWERX"
ID_PREFIX = "afwerx-"
DEPARTMENT = "Department of the Air Force"
TOPICS_URL = "https://www.dodsbirsttr.mil/topics-app/"   # DSIP's topic search: linked for people, never fetched
EASTERN = ZoneInfo("America/New_York")
MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september",
          "october", "november", "december")
DAY_MONTH_YEAR = re.compile(r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4}|\d{2})")
NOT_SET = re.compile(r"(?i)n/?a|tb[ad]|to be (?:announced|determined)")   # AFWERX has not set the date yet
KINDS = {"SBIR/STTR cycle": "An SBIR/STTR solicitation cycle", "STTR cycle": "An STTR solicitation cycle",
         "SBIR cycle": "An SBIR solicitation cycle", "Solicitation": "A solicitation"}
DSIP_NOTE = ("AFWERX lists solicitations, not their topics. The topics are on DSIP, the Defense Department's "
             "portal for these solicitations, which the scanner does not read: the call's link opens DSIP's "
             "topic search.")


def parse_date(text: Any) -> date | None:
    """ "7 Oct 26", "13 APRIL 26" or "6 Sept. 2027" as a date; None for TBD, N/A or anything else."""
    found = DAY_MONTH_YEAR.fullmatch(" ".join(str(text or "").split()))
    if not found:
        return None
    day, word, year = found.groups()
    month = next((n for n, name in enumerate(MONTHS, 1) if name.startswith(word.lower())), None)
    if month is None:
        return None
    try:
        return date(int(year) + (2000 if len(year) == 2 else 0), month, int(day))
    except ValueError:
        return None


def derive_type(title: str) -> str:
    words = title.lower()
    sbir, sttr = "sbir" in words, "sttr" in words
    if sbir and sttr:
        return "SBIR/STTR cycle"
    if sttr:
        return "STTR cycle"
    return "SBIR cycle" if sbir else "Solicitation"


def _shown(text: Any) -> str:
    """A date as "7 Oct 2026", or AFWERX's own wording when it is not a date."""
    parsed = parse_date(text)
    return f"{parsed.day} {MONTHS[parsed.month - 1][:3].title()} {parsed.year}" if parsed else str(text).strip()


def describe(cycle: dict[str, Any], kind: str) -> str:
    branches = cycle.get("branches") or []
    topics = f", with U.S. {' and '.join(branches)} topics" if branches else ""
    dates = ", ".join(f"{name} {_shown(cycle.get(key))}"
                      for name, key in (("pre-release", "pre_release"), ("opens", "open"), ("closes", "close"))
                      if str(cycle.get(key) or "").strip())
    dated = f"{dates[:1].upper()}{dates[1:]}. " if dates else ""
    return f"{KINDS[kind]} listed on AFWERX's Get Funded page{topics}. {dated}{DSIP_NOTE}"


def build_record(cycle: dict[str, Any], now: datetime) -> dict[str, Any]:
    title = " ".join(str(cycle.get("title") or "").split())
    if not title:
        raise ValueError("the cycle has no title")
    pre_release, opens, closes = (parse_date(cycle.get(key)) for key in ("pre_release", "open", "close"))
    posted = pre_release or opens
    kind = derive_type(title)
    return {
        "id": ID_PREFIX + re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-"),
        "portal": PORTAL,
        "title": title,
        "type": kind,
        "department": DEPARTMENT,
        "naics_code": "",
        "set_aside": "",
        "posted_date": posted.isoformat() if posted else "",
        "due_date": closes.isoformat() if closes else "",
        "description": describe(cycle, kind),
        "url": TOPICS_URL,
        "source_type": "scrape",
        "extra": {
            "afwerx_branches": list(cycle.get("branches") or []),
            "afwerx_pre_release": pre_release.isoformat() if pre_release else None,
            "afwerx_open": opens.isoformat() if opens else None,
            # TBD or N/A: no deadline yet by design. A close date that cannot be read is not, so the
            # scan quality alert still counts it.
            "afwerx_no_deadline": bool(NOT_SET.fullmatch(str(cycle.get("close") or "").strip())),
            "afwerx_closed": bool(closes and closes < now.astimezone(EASTERN).date()),
        },
    }
