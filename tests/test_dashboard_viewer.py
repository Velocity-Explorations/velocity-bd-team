"""Who is deciding, from the account menu (PRO-553, PRO-570): choosing a name applies at once, and
Log out clears it and returns to Home with its notice.

Loads the dashboard in headless Chromium and only sets or clears the viewer cookie, so it never
writes to the ledger. Name a serving dashboard in DASHBOARD_TEST_URL; without it the test is skipped.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

URL = os.environ.get("DASHBOARD_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_TEST_URL to a running dashboard")


def settle(page: Any) -> None:
    page.wait_for_timeout(2000)   # the menu's form has been sent
    page.reload(wait_until="load")
    page.wait_for_timeout(1000)


def account(page: Any) -> Any:
    return page.locator(".topbar details.account")


def test_choosing_a_name_applies_at_once_and_log_out_clears_it() -> None:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page: Any = browser.new_page()
        page.goto(URL + "/review", wait_until="load", timeout=120_000)
        menu = account(page)
        menu.locator("summary").click()
        names = menu.locator("form.choose-viewer button[name=viewer]")
        if names.count() == 0:
            browser.close()
            pytest.skip("this dashboard has nobody to choose: DASHBOARD_USERS names fewer than two people")
        name = names.first.get_attribute("value")
        names.first.click()
        settle(page)
        chosen = account(page).locator("summary .account-name").inner_text().strip()
        account(page).locator("summary").click()
        account(page).get_by_role("button", name="Log out").click()
        page.wait_for_url("**/?notice=*", timeout=10_000)
        notice = page.locator(".notice").inner_text()
        login = account(page).locator("summary").inner_text().strip()
        browser.close()
    assert chosen == name
    assert "You are logged out of BD Team." in notice
    assert login == "Log in"
