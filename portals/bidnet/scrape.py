"""Read the last eight days of BidNet Direct's Colorado and Florida bids into the ledger.

    counts = fetch_all(run_id)   # {"found", "scraped", "new", "failed"}

Each run reads the bids published in the last LOOKBACK_DAYS, newest first, so a weekly scan
sees each bid once with a day to spare and the first run posts no backlog of older open bids.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from ledger.queries import get_call, upsert_call
from portals.bidnet.api import STATES, Opener, Throttle, fetch_state
from portals.bidnet.records import build_record

LOOKBACK_DAYS = 8
DENVER = ZoneInfo("America/Denver")

log = logging.getLogger("bidnet.scrape")


def fetch_all(run_id: int, limit: int | None = None, now: datetime | None = None, opener: Opener | None = None,
              sleep: Callable[[float], None] | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    cutoff = now.astimezone(DENVER).date() - timedelta(days=LOOKBACK_DAYS)
    gate = Throttle(sleep=sleep or time.sleep)
    bids = [bid for state in STATES for bid in fetch_state(state, cutoff, opener, gate)]
    counts = {"found": len(bids), "scraped": 0, "new": 0, "failed": 0}
    skipped = 0
    for bid in bids:
        if limit is not None and counts["scraped"] >= limit:
            break
        try:
            record = build_record(bid, now)
        except (KeyError, TypeError, ValueError) as exc:
            counts["failed"] += 1
            log.warning("Could not read bid %s: %s: %s", bid.get("bid_id"), type(exc).__name__, str(exc)[:120])
            continue
        if record["extra"]["bidnet_closed"] and get_call(record["id"]) is None:
            skipped += 1
            continue
        counts["scraped"] += 1
        if upsert_call(record, run_id):
            counts["new"] += 1
    log.info("BidNet Direct: %d bids published since %s, %d stored (%d new), %d closed and never stored, %d unreadable",
             counts["found"], cutoff.isoformat(), counts["scraped"], counts["new"], skipped, counts["failed"])
    return counts
