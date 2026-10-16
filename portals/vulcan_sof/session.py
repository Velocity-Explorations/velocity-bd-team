"""Persist the Vulcan SOF browser session so repeat runs skip the emailed code.

    save_cookies(context)          # after every successful login or scrape
    if load_cookies(context): ...  # before trying the password at all

Cookies live in data/vulcan_cookies.json (git-ignored). Neither function raises: a
missing, empty or unreadable file simply means "log in the long way".
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from playwright.sync_api import BrowserContext

log = logging.getLogger("vulcan_sof.session")

REPO_ROOT = Path(__file__).resolve().parents[2]
COOKIE_FILE = REPO_ROOT / "data" / "vulcan_cookies.json"


def save_cookies(context: BrowserContext, path: Path = COOKIE_FILE) -> bool:
    """Write the context's cookies as JSON. Returns True on success; logs and returns False otherwise."""
    try:
        cookies = context.cookies()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        log.info("Saved %d cookies to %s", len(cookies), path.name)
        return True
    except Exception as exc:
        log.warning("Could not save cookies (%s: %s)", type(exc).__name__, str(exc)[:120])
        return False


def load_cookies(context: BrowserContext, path: Path = COOKIE_FILE) -> bool:
    """Add saved cookies to the context. True only when a non-empty list was loaded."""
    try:
        if not path.exists():
            log.info("No cookie file at %s", path.name)
            return False
        cookies = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cookies, list) or not cookies:
            log.info("Cookie file %s is empty", path.name)
            return False
        context.add_cookies(cookies)
        log.info("Loaded %d cookies from %s", len(cookies), path.name)
        return True
    except Exception as exc:
        log.warning("Could not load cookies (%s: %s)", type(exc).__name__, str(exc)[:120])
        return False


def clear_cookies(path: Path = COOKIE_FILE) -> None:
    """Delete the cookie file if present. Never raises."""
    try:
        path.unlink(missing_ok=True)
        log.info("Removed %s", path.name)
    except Exception as exc:
        log.warning("Could not remove cookie file (%s)", type(exc).__name__)
