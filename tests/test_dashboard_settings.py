"""The Settings dialog chooses which columns the review queue shows, for this browser (PRO-555).

Loads the dashboard in headless Chromium and only sets or clears the settings cookie, so it never
writes to the ledger. Name a serving dashboard in DASHBOARD_TEST_URL; without it the test is skipped.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

URL = os.environ.get("DASHBOARD_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_TEST_URL to a running dashboard")


def headers(page: Any) -> list[str]:
    return [text.strip() for text in page.locator("table thead th").all_inner_texts()]


def reloaded(page: Any) -> list[str]:
    page.wait_for_timeout(2000)   # the dialog's form has been sent
    page.reload(wait_until="load")
    page.wait_for_timeout(1000)
    return headers(page)


def test_settings_hide_a_column_and_reset_restores_the_defaults() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page: Any = browser.new_page(viewport={"width": 1440, "height": 900})
        page.goto(URL + "/", wait_until="load", timeout=120_000)
        if page.locator("table").count() == 0:
            browser.close()
            pytest.skip("the review queue is empty, so it has no columns to check")
        page.wait_for_timeout(1000)
        first = headers(page)
        page.get_by_role("button", name="Settings").click()
        page.locator("dialog.settings").get_by_label("AI reason").uncheck()
        page.locator("dialog.settings").get_by_role("button", name="Save").click()
        after_save = reloaded(page)
        page.get_by_role("button", name="Settings").click()
        page.locator("dialog.settings").get_by_role("button", name="Reset to defaults").click()
        after_reset = reloaded(page)
        browser.close()
    assert "Tier" not in first and "AI reason" in first
    assert "AI reason" not in after_save and "Call" in after_save
    assert after_reset == first
