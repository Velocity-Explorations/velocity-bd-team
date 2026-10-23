"""Read DIU's open solicitations into the ledger.

    counts = fetch_all(run_id)   # {"found", "scraped", "new", "failed"}

A solicitation whose close time has passed is skipped unless an earlier run stored it: that row
is still refreshed, so it shows as closed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ledger.queries import get_call, upsert_call
from portals.diu.api import Opener, fetch_page, open_solicitations
from portals.diu.records import build_record

log = logging.getLogger("diu.scrape")


def fetch_all(run_id: int, limit: int | None = None, now: datetime | None = None,
              opener: Opener | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    solicitations = open_solicitations(fetch_page(opener))
    counts = {"found": len(solicitations), "scraped": 0, "new": 0, "failed": 0}
    skipped = 0
    for aoi in solicitations:
        if limit is not None and counts["scraped"] >= limit:
            break
        try:
            record = build_record(aoi, now)
        except (KeyError, TypeError, ValueError) as exc:
            counts["failed"] += 1
            log.warning("Could not read solicitation %s: %s: %s", aoi.get("number"), type(exc).__name__, str(exc)[:120])
            continue
        if record["extra"]["diu_closed"] and get_call(record["id"]) is None:
            skipped += 1
            continue
        counts["scraped"] += 1
        if upsert_call(record, run_id):
            counts["new"] += 1
    log.info("DIU: %d solicitations, %d stored (%d new), %d closed and never stored, %d unreadable",
             counts["found"], counts["scraped"], counts["new"], skipped, counts["failed"])
    return counts
