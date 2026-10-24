"""Read NASA's acquisition forecast into the ledger.

    counts = fetch_all(run_id)   # {"found", "scraped", "new", "failed"}

A row NASA marks awarded, withdrawn or cancelled is skipped unless an earlier run stored it:
that row is still refreshed, so it shows as closed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ledger.queries import get_call, upsert_call
from portals.nasa_forecast.api import Opener, fetch_workbook, read_rows
from portals.nasa_forecast.records import build_record

log = logging.getLogger("nasa_forecast.scrape")


def fetch_all(run_id: int, limit: int | None = None, now: datetime | None = None,
              opener: Opener | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    rows = read_rows(fetch_workbook(opener))
    counts = {"found": len(rows), "scraped": 0, "new": 0, "failed": 0}
    skipped = 0
    for row in rows:
        if limit is not None and counts["scraped"] >= limit:
            break
        try:
            record = build_record(row, now)
        except (KeyError, TypeError, ValueError) as exc:
            counts["failed"] += 1
            log.warning("Could not read forecast row %s: %s: %s", row.get("SourceID"), type(exc).__name__, str(exc)[:120])
            continue
        if record["extra"]["nasa_closed"] and get_call(record["id"]) is None:
            skipped += 1
            continue
        counts["scraped"] += 1
        if upsert_call(record, run_id):
            counts["new"] += 1
    log.info("NASA Forecast: %d rows, %d stored (%d new), %d awarded, withdrawn or cancelled and never stored, "
             "%d unreadable", counts["found"], counts["scraped"], counts["new"], skipped, counts["failed"])
    return counts
