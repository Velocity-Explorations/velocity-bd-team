"""Enumerate open Vulcan SOF calls and read each one into the ledger.

    calls = list_calls(page)                 # [{"title", "href"}, ...] from the calls listing's links
    record = scrape_call(page, href, title)  # dict matching ledger `calls` columns, or None
    counts = scrape_all(page, run_id)        # {"found", "scraped", "new", "failed"}

Since Vulcan's redesign (found 16 Nov 2026) a call is read from the call feed its own page loads, through the logged-in
session (fetch_feed), not from the page text: the feed keeps the deadline's time, which the new pages no longer show.
records.py turns a feed item into a row. Every navigation, wait and request carries a timeout; never networkidle.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from ledger.queries import get_call, upsert_call
from portals.vulcan_sof.auth import CALLS_URL
from portals.vulcan_sof.records import DEFAULT_TYPE, DEPARTMENT, PORTAL, build_record   # noqa: F401  (re-exported)

log = logging.getLogger("vulcan_sof.scrape")

PAGE_GAP_MS = 300
FEED_URL = "https://vulcan-sof.com/apiv1/call/get"
FEED_TIMEOUT_MS = 15_000
REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "data" / "samples"
SAMPLE_COUNT = 3

# A call's uuid: in ?collectionUuid=<uuid> links until 16 Nov 2026, in /call/<uuid> links (and /call/<uuid>/about pages)
# since. The uuid is the same either way, so a call keeps its id.
UUID_RE = re.compile(r"(?:collectionUuid=|/call/)([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})")

LISTING_WAIT_MS = 20_000
LISTING_SETTLE_MS = 2_000
LINKS_SHOWN_JS = """() => document.querySelectorAll('a[href*="collectionUuid"], a[href*="/call/"]').length > 0"""
LIST_JS = """
() => Array.from(document.querySelectorAll('a[href*="collectionUuid"], a[href*="/call/"]'))
        .map(a => ({text: (a.innerText || '').trim(), href: a.href}))
"""


# ------------------------------------------------------------------- ids

def call_id_for(url: str) -> str:
    m = UUID_RE.search(url)
    if m:
        return f"vulcan-{m.group(1)}"
    return "vulcan-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


# ------------------------------------------------------------------------ browser side

def list_calls(page: Page) -> list[dict[str, str]]:
    """Every call link on the listing, one entry per call (the cards carry duplicate anchors)."""
    page.goto(CALLS_URL, timeout=20_000, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except Exception:
        pass
    # Since 16 Nov 2026 the cards draw some seconds after the page loads, so wait for the first call link rather than a
    # fixed time, then let the rest of the cards land.
    try:
        page.wait_for_function(LINKS_SHOWN_JS, timeout=LISTING_WAIT_MS)
    except Exception:
        log.warning("No call links on the listing after %.0f s", LISTING_WAIT_MS / 1000)
    page.wait_for_timeout(LISTING_SETTLE_MS)
    raw = page.evaluate(LIST_JS)
    by_id: dict[str, dict[str, str]] = {}
    for item in raw:
        if not item.get("text") or not item.get("href"):
            continue
        key = call_id_for(item["href"])
        if key not in by_id:
            by_id[key] = {"title": item["text"], "href": item["href"]}
    log.info("Listing: %d anchors, %d calls", len(raw), len(by_id))
    return list(by_id.values())


def fetch_feed(page: Page, uuid: str) -> dict[str, Any]:
    """The call's feed item, read through the logged-in session as the call's own page reads it. Raises on any failure."""
    response = page.context.request.get(FEED_URL, params={"uuid": uuid}, timeout=FEED_TIMEOUT_MS)
    if not response.ok:
        raise RuntimeError(f"call feed answered {response.status}")
    feed = response.json()
    if not isinstance(feed, dict) or feed.get("uuid") != uuid:
        raise RuntimeError("call feed returned something other than this call")
    return feed


def scrape_call(page: Page, href: str, title: str, sample_path: Path | None = None) -> dict[str, Any] | None:
    """One call, from its feed, to one record. Any failure logs a WARNING and returns None."""
    found = UUID_RE.search(href)
    if not found:
        log.warning("No call id in '%s'", href[:80])
        return None
    try:
        feed = fetch_feed(page, found.group(1))
        if not str(feed.get("name") or "").strip():
            feed = {**feed, "name": title}
        if sample_path is not None:
            sample_path.parent.mkdir(parents=True, exist_ok=True)
            sample_path.write_text(json.dumps(feed, indent=1), encoding="utf-8")
        known = get_call(call_id_for(href))
        return build_record(feed, href, datetime.now(timezone.utc), known_type=known["type"] if known else None)
    except Exception as exc:
        log.warning("Failed to read '%s': %s: %s", title[:40], type(exc).__name__, str(exc)[:120])
        return None


def scrape_all(page: Page, run_id: int, save_samples: bool = True, limit: int | None = None) -> dict[str, int]:
    """List, scrape each call, upsert into the ledger. Never aborts on a single bad page."""
    calls = list_calls(page)
    if limit is not None:
        calls = calls[:limit]
    counts = {"found": len(calls), "scraped": 0, "new": 0, "failed": 0}
    started = time.time()
    for n, call in enumerate(calls, start=1):
        sample = SAMPLES_DIR / f"call_{n}.json" if save_samples and n <= SAMPLE_COUNT else None
        record = scrape_call(page, call["href"], call["title"], sample)
        if record is None:
            counts["failed"] += 1
        else:
            counts["scraped"] += 1
            if upsert_call(record, run_id):
                counts["new"] += 1
        if n % 10 == 0 or n == len(calls):
            log.info("Scraped %d/%d (%d new, %d failed) in %.0fs", n, len(calls), counts["new"], counts["failed"], time.time() - started)
        page.wait_for_timeout(PAGE_GAP_MS)
    return counts
