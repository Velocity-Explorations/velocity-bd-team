"""Headless Chromium for the Vulcan SOF adapter.

Rules for every caller (from the 2026-04-18 three-day hang, see
reference/yukon/2026-04-18_vulcan-sof-hanging.md):

- Never wait for "networkidle" on this site. The Angular app keeps XHR and WebSocket
  traffic alive, so it never fires. Use wait_for_load_state("domcontentloaded") plus a
  fixed wait_for_timeout() of 1500 to 3000 ms.
- Every navigation and every wait carries an explicit timeout. The page defaults set
  here (DEFAULT_TIMEOUT_MS, NAV_TIMEOUT_MS) are a floor, not a licence to omit them.

Playwright's Chromium shows up as chrome.exe in Task Manager.
"""
from __future__ import annotations

import subprocess
import sys
import threading
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, Playwright, sync_playwright

LAUNCH_TIMEOUT_MS = 15_000
DEFAULT_TIMEOUT_MS = 15_000
NAV_TIMEOUT_MS = 30_000
VIEWPORT = {"width": 1366, "height": 900}

# The browser currently open, so force_close() can reach it from a watchdog thread.
_active_browser: Browser | None = None
_lock = threading.Lock()


def launch(headless: bool = True) -> tuple[Playwright, Browser, BrowserContext, Page]:
    """Start Playwright and Chromium. The launch itself is capped at LAUNCH_TIMEOUT_MS."""
    global _active_browser
    pw = sync_playwright().start()
    try:
        browser = pw.chromium.launch(headless=headless, timeout=LAUNCH_TIMEOUT_MS)
    except Exception:
        _quiet(pw.stop)
        raise
    with _lock:
        _active_browser = browser
    try:
        context = browser.new_context(viewport=VIEWPORT)
        page = context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
    except Exception:
        close_all(pw, browser)
        raise
    return pw, browser, context, page


def close_all(
    pw: Playwright | None,
    browser: Browser | None,
    context: BrowserContext | None = None,
    page: Page | None = None,
) -> None:
    """Close page, context, browser and Playwright in that order. Never raises."""
    global _active_browser
    if page is not None:
        _quiet(page.close)
    if context is not None:
        _quiet(context.close)
    if browser is not None:
        _quiet(browser.close)
    if pw is not None:
        _quiet(pw.stop)
    with _lock:
        if browser is None or _active_browser is browser:
            _active_browser = None


def force_close(kill_orphans: bool = True) -> bool:
    """Close the active browser from any thread. Never raises. Returns True if one was open.

    Used by the pipeline's watchdog when a portal run overruns its budget. The sync
    Playwright API refuses calls from a thread other than the one that launched the
    browser, so the close is best effort. Afterwards, on Windows, any Chromium that Playwright launched
    (chrome.exe under the ms-playwright directory, never the user's own Chrome) is killed
    so a hung browser cannot outlive the run.
    """
    global _active_browser
    with _lock:
        browser = _active_browser
        _active_browser = None
    had_browser = browser is not None
    if browser is not None:
        # From the owning thread this closes cleanly. From another thread Playwright's
        # sync API refuses the call (caught here) and the process kill below takes over.
        _quiet(browser.close)
    if kill_orphans:
        kill_playwright_chromium()
    return had_browser


def kill_playwright_chromium() -> None:
    """Terminate chrome.exe processes that live under the ms-playwright browser cache. Never raises."""
    if sys.platform != "win32":
        return
    script = (
        "Get-Process chrome -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Path -like '*ms-playwright*' } | "
        "Stop-Process -Force -ErrorAction SilentlyContinue"
    )
    try:
        subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, timeout=20)
    except Exception:
        pass


def playwright_chromium_pids() -> list[int]:
    """PIDs of Playwright-launched chrome.exe processes (Windows), for the hang check."""
    if sys.platform != "win32":
        return []
    script = (
        "Get-Process chrome -ErrorAction SilentlyContinue | "
        "Where-Object { $_.Path -like '*ms-playwright*' } | "
        "ForEach-Object { $_.Id }"
    )
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", script], capture_output=True, text=True, timeout=20)
        return [int(x) for x in out.stdout.split() if x.strip().isdigit()]
    except Exception:
        return []


def _quiet(fn: Any) -> None:
    try:
        fn()
    except Exception:
        pass
