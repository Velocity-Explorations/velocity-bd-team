"""Enumerate open Vulcan SOF calls and scrape each detail page into the ledger.

    calls = list_calls(page)                 # [{"title", "href"}, ...]
    record = scrape_call(page, href, title)  # dict matching ledger `calls` columns, or None
    counts = scrape_all(page, run_id)        # {"found", "scraped", "new", "failed"}

Detail pages have no stable CSS hooks, so fields are regexes over document.body.innerText.
The patterns are the ones the reference adapter proved (reference/yukon/vulcan_sof.py).
Every navigation and wait carries a timeout; never networkidle.
"""
from __future__ import annotations

import hashlib
import logging
import re
import time
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from ledger.queries import upsert_call
from portals.vulcan_sof.auth import CALLS_URL

log = logging.getLogger("vulcan_sof.scrape")

PORTAL = "Vulcan SOF"
DEPARTMENT = "USSOCOM / SOF Enterprise"
DEFAULT_TYPE = "Open Call"
PAGE_GAP_MS = 300
DETAIL_WAIT_MS = 1_500
REPO_ROOT = Path(__file__).resolve().parents[2]
SAMPLES_DIR = REPO_ROOT / "data" / "samples"
SAMPLE_COUNT = 3

DUE_RE = re.compile(r"Deadline[:\s]*([^\n]+(?:MDT|MST|EST|UTC|202[0-9]))")
OPEN_RE = re.compile(r"Open Date[:\s]*([^\n]+(?:MDT|MST|EST|UTC|202[0-9]))")
TYPE_RE = re.compile(r"Engagement Objectives?[:\s]*\n((?:[^\n]+\n?){1,5})")
# The spec's patterns required a blank line within 600 characters of the heading. On real
# pages the first paragraph is often 700 to 1,250 characters with no break, so instead we
# take up to 2,500 characters after the heading, collapse whitespace, and keep 1,500.
DESC_RES = [
    re.compile(r"Bottom Line Upfront\s*\n+([\s\S]{1,2500})"),
    re.compile(r"Problem Statement\s*\n+([\s\S]{1,2500})"),
]
DESC_MIN_CHARS = 40
DESC_MAX_CHARS = 1500   # was 400; the reviewer kept calling the text truncated
CLOSED_RE = re.compile(r"This call has closed", re.I)
UUID_RE = re.compile(r"collectionUuid=([a-f0-9-]{36})")
RENDERED_JS = "() => /Deadline|Open Date|Problem Statement/.test(document.body ? document.body.innerText : '')"
RENDER_EXTRA_WAIT_MS = 6_000

LIST_JS = """
() => Array.from(document.querySelectorAll('a[href*="collectionUuid"]'))
        .map(a => ({text: (a.innerText || '').trim(), href: a.href}))
"""


# ------------------------------------------------------------------- pure extraction

def call_id_for(url: str) -> str:
    m = UUID_RE.search(url)
    if m:
        return f"vulcan-{m.group(1)}"
    return "vulcan-" + hashlib.sha1(url.encode("utf-8")).hexdigest()[:16]


def extract_fields(body: str) -> dict[str, str]:
    """due_date, posted_date, type, description from a detail page's innerText."""
    due = DUE_RE.search(body)
    opened = OPEN_RE.search(body)
    typ = TYPE_RE.search(body)
    description = ""
    for pattern in DESC_RES:
        m = pattern.search(body)
        if m:
            candidate = " ".join(m.group(1).split())[:DESC_MAX_CHARS]
            if len(candidate) >= DESC_MIN_CHARS:
                description = candidate
                break
    return {
        "due_date": due.group(1).strip()[:40] if due else "",
        "posted_date": opened.group(1).strip()[:40] if opened else "",
        "type": typ.group(1).strip().split("\n")[0].strip()[:60] if typ else DEFAULT_TYPE,
        "description": description or body[200:600].strip(),
        "description_is_fallback": "" if description else "1",
        "closed": "1" if CLOSED_RE.search(body) else "",
    }


def build_record(url: str, title: str, body: str) -> dict[str, Any]:
    fields = extract_fields(body)
    return {
        "id": call_id_for(url),
        "title": title,
        "portal": PORTAL,
        "type": fields["type"],
        "department": DEPARTMENT,
        "naics_code": "",
        "set_aside": "",
        "posted_date": fields["posted_date"],
        "due_date": fields["due_date"],
        "description": fields["description"],
        "url": url,
        "source_type": "regular",
        "extra": {
            "vulcan_description_fallback": bool(fields["description_is_fallback"]),
            "vulcan_closed": bool(fields["closed"]),
        },
    }


# ------------------------------------------------------------------------ browser side

def list_calls(page: Page) -> list[dict[str, str]]:
    """Every call link on the listing, one entry per call (the cards carry duplicate anchors)."""
    page.goto(CALLS_URL, timeout=20_000, wait_until="domcontentloaded")
    try:
        page.wait_for_load_state("domcontentloaded", timeout=10_000)
    except Exception:
        pass
    page.wait_for_timeout(3_000)
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


def scrape_call(page: Page, href: str, title: str, sample_path: Path | None = None) -> dict[str, Any] | None:
    """One detail page to one record. Any failure logs a WARNING and returns None."""
    try:
        page.goto(href, timeout=15_000, wait_until="domcontentloaded")
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10_000)
        except Exception:
            pass
        page.wait_for_timeout(DETAIL_WAIT_MS)
        if not page.evaluate(RENDERED_JS):
            # A few pages render 1 to 2 s later than the rest; give them a bounded extra wait.
            try:
                page.wait_for_function(RENDERED_JS, timeout=RENDER_EXTRA_WAIT_MS)
            except Exception:
                log.warning("'%s' still not rendered after %.1fs", title[:40], (DETAIL_WAIT_MS + RENDER_EXTRA_WAIT_MS) / 1000)
        body = page.evaluate("() => document.body ? document.body.innerText : ''")
        if sample_path is not None:
            sample_path.parent.mkdir(parents=True, exist_ok=True)
            sample_path.write_text(body, encoding="utf-8")
        return build_record(href, title, body)
    except Exception as exc:
        log.warning("Failed to scrape '%s': %s: %s", title[:40], type(exc).__name__, str(exc)[:120])
        return None


def scrape_all(page: Page, run_id: int, save_samples: bool = True, limit: int | None = None) -> dict[str, int]:
    """List, scrape each call, upsert into the ledger. Never aborts on a single bad page."""
    calls = list_calls(page)
    if limit is not None:
        calls = calls[:limit]
    counts = {"found": len(calls), "scraped": 0, "new": 0, "failed": 0}
    started = time.time()
    for n, call in enumerate(calls, start=1):
        sample = SAMPLES_DIR / f"call_{n}.txt" if save_samples and n <= SAMPLE_COUNT else None
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
