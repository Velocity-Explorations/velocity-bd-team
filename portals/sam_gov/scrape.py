"""Read SAM.gov's open notices into the ledger, spending requests only where they are needed.

    counts = fetch_all(run_id)   # found, scraped, new, failed, dropped, reposts, pending, requests

One search per NAICS code in search.yaml, then one per office listed there (IARPA), whatever
its codes; a notice both find is kept once. Notices of a type or set-aside Velocity does not
pursue, or with a blocklisted title, are dropped before their description is read; so is a
notice Front Door already carries. A notice stored earlier is refreshed from the search result
(deadline, type, closed) without another request. New notices are read soonest deadline first,
until the run's budget, SAM.gov's daily limit or `limit` stops them; the rest are read on the
next run.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from config import require
from ledger.queries import get_call, sam_notices_on, upsert_call
from portals.sam_gov.api import Budget, Opener, SamError, SamQuota, description, ipv4_urlopen, search, search_office
from portals.sam_gov.records import KEYWORDS_PATH, SEARCH_PATH, build_record, deadline, keep, load_rules, notice_id
from portals.shared.keyword_filter import load_keywords

REQUEST_BUDGET = 900                     # of the key's 1,000 a day, leaving room for a rerun or a test
FRONT_DOOR = "SSC Front Door"            # its reposts of SAM.gov notices carry this extra key
FRONT_DOOR_KEY = "sscfd_sam_notice_id"
LAST = datetime.max.replace(tzinfo=timezone.utc)

log = logging.getLogger("sam_gov.scrape")


def _blocked(title: str, blocklist: list[Any]) -> str | None:
    hit = next((p for p in blocklist if p.search(title)), None)
    return f"blocklist: {hit.pattern}" if hit else None


def fetch_all(run_id: int, limit: int | None = None, now: datetime | None = None,
              opener: Opener | None = None, key: str | None = None) -> dict[str, int]:
    now = now or datetime.now(timezone.utc)
    key = key or require("BD_SAM_API_KEY")
    opener = opener or ipv4_urlopen
    rules = load_rules(SEARCH_PATH)
    blocklist = load_keywords(KEYWORDS_PATH).blocklist
    budget = Budget(REQUEST_BUDGET)
    counts = {"found": 0, "scraped": 0, "new": 0, "failed": 0, "dropped": 0, "reposts": 0, "pending": 0, "requests": 0}

    notices: dict[str, dict[str, Any]] = {}
    searches = [(search, code) for code in rules.naics_codes] + [(search_office, office) for office in rules.offices]
    try:
        for ask, value in searches:
            for raw in ask(value, now.date(), key, opener, budget):
                if notice_id(raw):
                    notices.setdefault(notice_id(raw), raw)   # the same notice can sit under two codes or an office
    except SamQuota as exc:
        log.warning("Searches stopped early: %s", exc)
    counts["found"] = len(notices)

    reposted = sam_notices_on(FRONT_DOOR, FRONT_DOOR_KEY)
    unread: list[dict[str, Any]] = []
    for nid, raw in notices.items():
        reason = keep(raw, rules) or _blocked(str(raw.get("title") or ""), blocklist)
        if reason:
            counts["dropped"] += 1
            log.debug("Dropped %s (%s)", nid, reason)
            continue
        if nid in reposted:
            counts["reposts"] += 1
            continue
        try:
            record = build_record(raw, now)
        except (KeyError, TypeError, ValueError) as exc:
            counts["failed"] += 1
            log.warning("Could not read notice %s: %s", nid, str(exc)[:120])
            continue
        if get_call(record["id"]) is not None:
            upsert_call(record, run_id)   # no description key: the stored text stays
            counts["scraped"] += 1
            continue
        unread.append(raw)

    unread.sort(key=lambda r: (deadline(r) or LAST, notice_id(r)))
    stopped: str | None = None
    for raw in unread:
        if stopped or (limit is not None and counts["new"] >= limit):
            counts["pending"] += 1
            continue
        try:
            text = description(raw.get("description"), key, opener, budget)
        except SamQuota as exc:
            stopped = str(exc)
            counts["pending"] += 1
            continue
        except SamError as exc:
            counts["failed"] += 1
            log.warning("Description of %s not read: %s", notice_id(raw), exc)
            continue
        counts["scraped"] += 1
        if upsert_call(build_record(raw, now, text), run_id):
            counts["new"] += 1
    counts["requests"] = budget.used
    if stopped:
        log.warning("Stopped reading descriptions: %s. %d notices wait for the next run.", stopped, counts["pending"])
    log.info("SAM.gov: %d open notices, %d dropped, %d on Front Door, %d stored (%d new), %d waiting, "
             "%d failed, %d requests", counts["found"], counts["dropped"], counts["reposts"], counts["scraped"],
             counts["new"], counts["pending"], counts["failed"], counts["requests"])
    return counts
