"""Smoke tests that start real headless Chromium. They need `playwright install chromium`."""
from __future__ import annotations

from portals.shared import browser


def test_launch_and_close_all() -> None:
    pw, b, ctx, page = browser.launch()
    try:
        assert b.is_connected()
        assert browser._active_browser is b
        assert page.evaluate("() => 1 + 1") == 2
    finally:
        browser.close_all(pw, b, ctx, page)
    assert browser._active_browser is None
    assert not b.is_connected()


def test_force_close_without_browser_is_quiet() -> None:
    browser._active_browser = None
    assert browser.force_close() is False


def test_force_close_closes_active_browser_and_close_all_still_quiet() -> None:
    pw, b, ctx, page = browser.launch()
    assert browser.force_close() is True
    assert browser._active_browser is None
    assert not b.is_connected()
    browser.close_all(pw, b, ctx, page)   # must not raise on already-closed objects
