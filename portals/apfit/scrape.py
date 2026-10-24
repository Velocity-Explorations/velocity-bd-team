"""Read the APFIT cycle-status posts into the ledger.

    counts = fetch_all(run_id)   # {"found", "scraped", "new", "failed"}

A closed cycle (final selection, evaluation, closed or awarded) is skipped unless an earlier run
stored it: that row is still refreshed, so it shows as closed.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from ledger.queries import get_call, upsert_call
from portals.apfit.api import Opener, cycle_posts, fetch_page
from portals.apfit.records import build_record

log = logging.getLogger("apfit.scrape")


def fetch_all(run_id: int, limit: int | None = None, now: datetime | None = None,
              opener: Opener | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    posts = cycle_posts(fetch_page(opener))
    counts = {"found": len(posts), "scraped": 0, "new": 0, "failed": 0}
    skipped = 0
    for post in posts:
        if limit is not None and counts["scraped"] >= limit:
            break
        try:
            record = build_record(post, now)
        except (KeyError, TypeError, ValueError) as exc:
            counts["failed"] += 1
            log.warning("Could not read post %r: %s: %s", post.get("title"), type(exc).__name__, str(exc)[:120])
            continue
        if record["extra"]["apfit_closed"] and get_call(record["id"]) is None:
            skipped += 1
            continue
        counts["scraped"] += 1
        if upsert_call(record, run_id):
            counts["new"] += 1
    log.info("APFIT: %d cycle posts, %d stored (%d new), %d closed and never stored, %d unreadable",
             counts["found"], counts["scraped"], counts["new"], skipped, counts["failed"])
    return counts
