"""Read the solicitations on DOE's SBIR/STTR Application Hub into the ledger.

    counts = fetch_all(run_id)   # {"found", "scraped", "new", "failed"}

A closed solicitation is skipped unless an earlier run stored it: that row is still refreshed,
so it shows as closed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ledger.queries import get_call, upsert_call
from portals.doe_sbir.api import Opener, fetch_items
from portals.doe_sbir.records import build_record

log = logging.getLogger("doe_sbir.scrape")


def fetch_all(run_id: int, limit: int | None = None, now: datetime | None = None,
              opener: Opener | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    items = fetch_items(opener)
    counts = {"found": len(items), "scraped": 0, "new": 0, "failed": 0}
    skipped = 0
    for item in items:
        if limit is not None and counts["scraped"] >= limit:
            break
        try:
            record = build_record(item, now)
        except (KeyError, TypeError, ValueError) as exc:
            counts["failed"] += 1
            log.warning("Could not read item %s: %s: %s", item.get("id"), type(exc).__name__, str(exc)[:120])
            continue
        if record["extra"]["doe_closed"] and get_call(record["id"]) is None:
            skipped += 1
            continue
        counts["scraped"] += 1
        if upsert_call(record, run_id):
            counts["new"] += 1
    log.info("DOE SBIR: %d solicitations, %d stored (%d new), %d closed and never stored, %d unreadable",
             counts["found"], counts["scraped"], counts["new"], skipped, counts["failed"])
    return counts
