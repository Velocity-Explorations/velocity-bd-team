"""Read the Front Door Events list into the ledger.

    counts = fetch_all(run_id)   # {"found", "scraped", "new", "failed"}

A listing that has already ended is skipped, unless an earlier run stored it: that row is
still refreshed, so it shows as closed. A repost of a SAM.gov notice the SAM.gov adapter
already stored is skipped too, so the notice gets one card (PRO-525).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ledger.queries import get_call, upsert_call
from portals.ssc_front_door.api import Opener, fetch_records
from portals.ssc_front_door.records import build_record

log = logging.getLogger("ssc_front_door.scrape")
SAM_GOV_PREFIX = "samgov-"   # the SAM.gov adapter's call ids


def fetch_all(run_id: int, limit: int | None = None, now: datetime | None = None,
              opener: Opener | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    listings = fetch_records(opener)
    counts = {"found": len(listings), "scraped": 0, "new": 0, "failed": 0}
    skipped = reposts = 0
    for listing in listings:
        if limit is not None and counts["scraped"] >= limit:
            break
        try:
            record = build_record(listing, now)
        except (KeyError, TypeError, ValueError) as exc:
            counts["failed"] += 1
            log.warning("Could not read listing %s: %s: %s", listing.get("contentKey"), type(exc).__name__, str(exc)[:120])
            continue
        if record["extra"]["sscfd_closed"] and get_call(record["id"]) is None:
            skipped += 1
            continue
        notice = record["extra"].get("sscfd_sam_notice_id")
        if notice and get_call(f"{SAM_GOV_PREFIX}{notice}") is not None and get_call(record["id"]) is None:
            reposts += 1   # SAM.gov's copy came first
            continue
        counts["scraped"] += 1
        if upsert_call(record, run_id):
            counts["new"] += 1
    log.info("Events list: %d listings, %d stored (%d new), %d ended and never stored, %d already on SAM.gov, "
             "%d unreadable", counts["found"], counts["scraped"], counts["new"], skipped, reposts, counts["failed"])
    return counts
