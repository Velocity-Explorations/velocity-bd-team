"""One APFIT cycle post to one `calls` row. Pure: no network, no ledger.

    rec = build_record(post, now)

A cycle post says where the cycle stands ("is open", "is in final selection", "Awards have been
announced"). There is no deadline to store: each participating organization sets its own. A
cycle counts as closed once its status says final selection, evaluation, closed or awarded.
"""
from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

PORTAL = "APFIT"
ID_PREFIX = "apfit-"
DEPARTMENT = "OUSW(R&E)"
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
CYCLE = re.compile(r"(?i)\bFY\s?(\d{2,4})-(\d)\b")
CLOSED = re.compile(r"(?i)final selection|\b(?:under|in) evaluation\b|\bclosed\b|\bawarded\b|\bawards?\b[^.]*\bannounced\b")
ABOUT = ("APFIT (Accelerate the Procurement and Fielding of Innovative Technologies) awards $10M to $50M to projects "
         "with small business or nontraditional performers to speed initial production. Proposals come from "
         "government sponsors through an approved service APFIT representative, and each participating "
         "organization sets its own deadlines.")


def is_closed(status: str) -> bool:
    return bool(CLOSED.search(status or ""))


def _shown(iso: str) -> str:
    try:
        day = date.fromisoformat(iso)
    except ValueError:
        return iso
    return f"{day.day} {MONTHS[day.month - 1]} {day.year}"


def build_record(post: dict[str, Any], now: datetime) -> dict[str, Any]:
    title = " ".join(str(post.get("title") or "").split())
    post_id = str(post.get("post_id") or "").strip()
    if not title or not (post_id or CYCLE.search(title)):
        raise ValueError("the post has no title or id")
    found = CYCLE.search(title)
    cycle = f"FY{found.group(1)}-{found.group(2)}" if found else ""
    status = " ".join(str(post.get("status") or "").split())
    as_of = str(post.get("modified") or post.get("published") or "")
    heading = f"{cycle} status" if cycle else "Status"
    when = f" on {_shown(as_of)}" if as_of else ""
    return {
        "id": f"{ID_PREFIX}{cycle.lower()}" if cycle else f"{ID_PREFIX}post-{post_id}",
        "portal": PORTAL,
        "title": f"APFIT {cycle} cycle" if cycle else title,
        "type": "APFIT cycle",
        "department": DEPARTMENT,
        "naics_code": "",
        "set_aside": "",
        "posted_date": str(post.get("published") or ""),
        "due_date": "",
        "description": f"{ABOUT}\n\n{heading}{when}: {status}" if status else ABOUT,
        "url": str(post.get("link") or "https://ac.cto.mil/apfit/"),
        "source_type": "scrape",
        "extra": {
            "apfit_cycle": cycle or None,
            "apfit_post_id": post_id or None,
            "apfit_status": status or None,
            "apfit_no_deadline": True,   # each participating organization sets its own deadline
            "apfit_closed": is_closed(status),
        },
    }
