"""Choosing a name under "Deciding as" applies it at once, and the button beside the picker
clears it (PRO-553).

Loads the dashboard in headless Chromium and only sets or clears the picker's cookie, so it never
writes to the ledger. Name a serving dashboard in DASHBOARD_TEST_URL; without it the test is skipped.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

URL = os.environ.get("DASHBOARD_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_TEST_URL to a running dashboard")


def chosen_after_reload(page: Any) -> str:
    page.wait_for_timeout(2000)   # the picker's form has been sent
    page.reload(wait_until="load")
    page.wait_for_timeout(1000)   # the page's script has loaded
    return page.locator("select#viewer").input_value()


def test_choosing_a_name_applies_at_once_and_the_button_clears_it() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page: Any = browser.new_page()
        page.goto(URL + "/", wait_until="load", timeout=120_000)
        if page.locator("select#viewer").count() == 0:
            browser.close()
            pytest.skip("this dashboard has no picker: DASHBOARD_USERS names fewer than two people")
        page.wait_for_timeout(1000)
        button = page.locator("form.viewer button")
        assert button.count() == 1 and button.inner_text().strip() == "Clear User Selection"
        name = page.locator("select#viewer option:not([disabled])").first.get_attribute("value")
        page.select_option("select#viewer", name)
        after_choosing = chosen_after_reload(page)
        page.locator("form.viewer button").click()
        after_clearing = chosen_after_reload(page)
        browser.close()
    assert (after_choosing, after_clearing) == (name, "")
