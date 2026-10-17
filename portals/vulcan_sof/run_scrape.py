"""Scrape every open Vulcan SOF call into the ledger.

    python -m portals.vulcan_sof.run_scrape

Logs in cookie-first, records a `runs` row, scrapes all calls, saves cookies, and prints
counts, elapsed time and the per-field fill rate for this run's rows.
"""
from __future__ import annotations

import logging
import sys
import time
import traceback

from config import ConfigError, require
from ledger.queries import calls_in_run, finish_run, start_run
from portals.shared.browser import close_all, launch
from portals.shared.session import save_cookies
from portals.vulcan_sof.auth import COOKIE_FILE, login
from portals.vulcan_sof.scrape import DEFAULT_TYPE, PORTAL, scrape_all

log = logging.getLogger("vulcan_sof.run")

FILL_FIELDS = ("due_date", "posted_date", "type", "description")


def fill_rates(rows: list[dict]) -> dict[str, float]:
    """Share of rows where each field is non-empty and not its fallback value."""
    if not rows:
        return {f: 0.0 for f in FILL_FIELDS}
    rates: dict[str, float] = {}
    for field in FILL_FIELDS:
        filled = 0
        for row in rows:
            value = (row.get(field) or "").strip()
            if not value:
                continue
            if field == "type" and value == DEFAULT_TYPE:
                continue
            if field == "description" and '"vulcan_description_fallback": true' in (row.get("extra") or ""):
                continue
            filled += 1
        rates[field] = 100.0 * filled / len(rows)
    return rates


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        username = require("VULCAN_SOF_USERNAME")
        password = require("VULCAN_SOF_PASSWORD")
    except ConfigError as exc:
        print(exc)
        return 2

    started = time.time()
    run_id = start_run(PORTAL, dry_run=False, component="vulcan_sof")
    log.info("Run %d started", run_id)
    pw, browser, context, page = launch()
    counts = {"found": 0, "scraped": 0, "new": 0, "failed": 0}
    try:
        if not login(page, context, username, password):
            finish_run(run_id, "error", counts, error="login failed")
            print("login failed; see log")
            return 1
        counts = scrape_all(page, run_id)
        save_cookies(context, COOKIE_FILE)
        finish_run(run_id, "completed", counts)
    except Exception:
        finish_run(run_id, "error", counts, error=traceback.format_exc()[-2000:])
        raise
    finally:
        close_all(pw, browser, context, page)

    elapsed = time.time() - started
    rows = calls_in_run(run_id)
    rates = fill_rates(rows)
    print(f"\nrun {run_id}: found={counts['found']} scraped={counts['scraped']} new={counts['new']} failed={counts['failed']}")
    print(f"elapsed: {elapsed:.0f} s")
    print("fill rate (this run's rows):")
    for field in FILL_FIELDS:
        print(f"  {field:12s} {rates[field]:5.1f}%")
    return 0


if __name__ == "__main__":
    sys.exit(main())
