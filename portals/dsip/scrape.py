"""Read the Defense Department's open SBIR and STTR topics into the ledger, one call a topic.

    counts = fetch_all(run_id)   # {"found", "scraped", "new", "failed"}

First the DOCX files a person dropped in data/dsip/inbox (inbox.py), then SBIR.gov's copy (sbirgov.py), so that where
both have a topic SBIR.gov's copy, with its exact dates, is the one kept. A closed topic is skipped unless an earlier run
stored it. Last, every stored DSIP call whose close date has passed is marked closed, since SBIR.gov stops listing a
topic once it closes.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from pathlib import Path

from ledger.queries import calls_on, get_call, upsert_call
from portals.dsip.inbox import FOLDER, import_inbox
from portals.dsip.records import EASTERN, PORTAL, from_sbirgov, read_topic_page
from portals.dsip.sbirgov import DELAY_S, Fetcher, Opener, SbirGovError, topic_links

log = logging.getLogger("dsip.scrape")


def close_past(run_id: int, now: datetime) -> int:
    """Mark closed every stored DSIP call past its close date; returns how many changed."""
    today = now.astimezone(EASTERN).date()
    changed = 0
    for call in calls_on([PORTAL]):
        try:
            due = date.fromisoformat(str(call["due_date"] or "")[:10])
        except ValueError:
            continue
        if due < today and not call["extra"].get("dsip_closed"):
            upsert_call({"id": call["id"], "extra": {**call["extra"], "dsip_closed": True}}, run_id)
            changed += 1
    return changed


def fetch_all(run_id: int, limit: int | None = None, now: datetime | None = None, opener: Opener | None = None,
              delay: float = DELAY_S, folder: Path | None = FOLDER) -> dict[str, int]:
    """`folder` holds the inbox (None skips it); `limit` caps the SBIR.gov topics read, for a dry run."""
    now = now or datetime.now(timezone.utc)
    counts = {"found": 0, "scraped": 0, "new": 0, "failed": 0}
    if folder is not None:
        for key, value in import_inbox(run_id, folder=folder, now=now).items():
            counts[key] += value
    fetcher = Fetcher(opener, delay)
    links = topic_links(fetcher)
    counts["found"] += len(links)
    tried = skipped = 0
    for link in links:
        if limit is not None and tried >= limit:
            break
        tried += 1
        try:
            record = from_sbirgov(read_topic_page(fetcher.get(link)), link, now)
        except (SbirGovError, ValueError, KeyError) as exc:
            counts["failed"] += 1
            log.warning("Could not read %s: %s: %s", link, type(exc).__name__, str(exc)[:120])
            continue
        if record["extra"]["dsip_closed"] and get_call(record["id"]) is None:
            skipped += 1
            continue
        counts["scraped"] += 1
        if upsert_call(record, run_id):
            counts["new"] += 1
    closed = close_past(run_id, now)
    log.info("DSIP: %d topics on SBIR.gov and in the inbox, %d stored (%d new), %d closed and never stored, %d unreadable, "
             "%d stored topics now closed", counts["found"], counts["scraped"], counts["new"], skipped, counts["failed"], closed)
    return counts
