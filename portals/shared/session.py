"""Saved browser sessions, so a portal's repeat runs skip its emailed sign-in code.

    COOKIE_FILE = cookie_path("vulcan_sof")     # data/vulcan_sof/cookies.json
    if load_cookies(context, COOKIE_FILE): ...  # before trying the password at all
    save_cookies(context, COOKIE_FILE)          # after every successful login or scrape

Each portal keeps its cookies in its own data folder (AGENTS.md rule 6), git-ignored.
None of these raise: a missing, empty or unreadable file simply means "log in the long way".
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from playwright.sync_api import BrowserContext

log = logging.getLogger("portals.session")

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"


def cookie_path(slug: str) -> Path:
    """Where a portal's saved cookies live: data/<slug>/cookies.json."""
    return DATA_DIR / slug / "cookies.json"


def _label(path: Path) -> str:
    return f"{path.parent.name}/{path.name}"


def save_cookies(context: BrowserContext, path: Path) -> bool:
    """Write the context's cookies as JSON. Returns True on success; logs and returns False otherwise."""
    try:
        cookies = context.cookies()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        log.info("Saved %d cookies to %s", len(cookies), _label(path))
        return True
    except Exception as exc:
        log.warning("Could not save cookies (%s: %s)", type(exc).__name__, str(exc)[:120])
        return False


def load_cookies(context: BrowserContext, path: Path) -> bool:
    """Add saved cookies to the context. True only when a non-empty list was loaded."""
    try:
        if not path.exists():
            log.info("No saved cookies at %s", _label(path))
            return False
        cookies = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(cookies, list) or not cookies:
            log.info("Saved cookies at %s are empty", _label(path))
            return False
        context.add_cookies(cookies)
        log.info("Loaded %d cookies from %s", len(cookies), _label(path))
        return True
    except Exception as exc:
        log.warning("Could not load cookies (%s: %s)", type(exc).__name__, str(exc)[:120])
        return False


def clear_cookies(path: Path) -> None:
    """Delete the saved cookies if present, forcing a full login next time. Never raises."""
    try:
        path.unlink(missing_ok=True)
        log.info("Removed %s", _label(path))
    except Exception as exc:
        log.warning("Could not remove saved cookies (%s)", type(exc).__name__)
