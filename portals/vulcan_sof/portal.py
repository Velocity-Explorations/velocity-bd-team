"""The Vulcan SOF portal as the pipeline sees it (see portals/registry.py for the contract)."""
from __future__ import annotations

import logging
from typing import Any

from playwright.sync_api import Page

from config import require
from portals.vulcan_sof.auth import login
from portals.vulcan_sof.filter import filter_calls
from portals.vulcan_sof.scrape import PORTAL as PORTAL_NAME
from portals.vulcan_sof.scrape import scrape_all
from portals.vulcan_sof.session import save_cookies

log = logging.getLogger("vulcan_sof.portal")


class LoginFailed(RuntimeError):
    """login() returned False. The pipeline treats this as a fetch error and alerts."""


def fetch(page: Page, run_id: int, limit: int | None = None) -> dict[str, int]:
    """Log in cookie-first, scrape every call into the ledger, save cookies. Raises LoginFailed."""
    if not login(page, page.context, require("VULCAN_SOF_USERNAME"), require("VULCAN_SOF_PASSWORD")):
        raise LoginFailed("Vulcan SOF login returned False")
    counts = scrape_all(page, run_id, limit=limit)
    save_cookies(page.context)
    return counts


def filter_rows(rows: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    return filter_calls(rows)


PORTAL = {
    "slug": "vulcan_sof",
    "name": PORTAL_NAME,
    "fetch": fetch,
    "filter": filter_rows,
    "fetch_timeout": 300,
    "needs_browser": True,
}
