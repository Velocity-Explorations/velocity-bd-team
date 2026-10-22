"""Read NSTXL's opportunities into the ledger.

    counts = fetch_all(run_id)   # {"found", "scraped", "new", "failed"}

Every opportunity post is read (about three pages). An item that is not open, or whose deadline
has passed, is skipped unless an earlier run stored it: that row is still refreshed, so it shows
as closed.
"""
from __future__ import annotations

import logging
import urllib.request
from datetime import datetime, timezone

from ledger.queries import get_call, upsert_call
from portals.nstxl.api import Opener, fetch_opportunities, fetch_terms
from portals.nstxl.records import build_record

log = logging.getLogger("nstxl.scrape")


def fetch_all(run_id: int, limit: int | None = None, now: datetime | None = None,
              opener: Opener | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    opener = opener or urllib.request.urlopen
    statuses = fetch_terms("opp_status", opener)
    otas = fetch_terms("ota", opener)
    items = fetch_opportunities(opener)
    counts = {"found": len(items), "scraped": 0, "new": 0, "failed": 0}
    skipped = members = 0
    for item in items:
        if limit is not None and counts["scraped"] >= limit:
            break
        try:
            record = build_record(item, statuses, otas, now)
        except (KeyError, TypeError, ValueError) as exc:
            counts["failed"] += 1
            log.warning("Could not read opportunity %s: %s: %s", item.get("id"), type(exc).__name__, str(exc)[:120])
            continue
        if record["extra"]["nstxl_closed"] and get_call(record["id"]) is None:
            skipped += 1
            continue
        counts["scraped"] += 1
        members += bool(record["extra"]["nstxl_members_only"])
        if upsert_call(record, run_id):
            counts["new"] += 1
    log.info("NSTXL: %d posts, %d stored (%d new, %d member-only), %d not open and never stored, %d unreadable",
             counts["found"], counts["scraped"], counts["new"], members, skipped, counts["failed"])
    return counts
