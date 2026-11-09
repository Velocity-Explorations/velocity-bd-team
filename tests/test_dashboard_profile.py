"""Profile settings (PRO-574): the page asks a person to log in first, then shows one row per setting,
and the account menu links to it. These tests only set the viewer cookie in their own browser; they
never save a profile, which would overwrite a real person's settings in the ledger.

Name a serving dashboard in DASHBOARD_TEST_URL; without it they are skipped.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

URL = os.environ.get("DASHBOARD_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_TEST_URL to a running dashboard")

SETTINGS = ["Name", "Picture", "Signed-in account", "Where the dashboard opens", "Default filters for Calls", "Time zone"]


@pytest.fixture()
def page() -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page(viewport={"width": 1440, "height": 900})
        browser.close()


def log_in(page: Any) -> bool:
    """Choose the first allowed name in the account menu; False when there is nobody to choose."""
    page.goto(URL + "/review", wait_until="load", timeout=120_000)
    menu = page.locator(".topbar details.account")
    menu.locator("summary").click()
    names = menu.locator("form.choose-viewer button[name=viewer]")
    if names.count() == 0:
        return False
    names.first.click()
    page.wait_for_timeout(2000)
    return True


def test_profile_settings_asks_to_log_in_first(page: Any) -> None:
    page.goto(URL + "/profile", wait_until="load", timeout=120_000)
    if page.locator(".topbar details.account summary.btn-primary").count() == 0:
        pytest.skip("someone is always deciding on this dashboard")
    assert "Log in (top right) to set your profile." in page.locator("main").inner_text()
    assert page.locator(".topbar nav a[aria-current=page]").count() == 0


def test_profile_settings_shows_each_setting_and_the_menu_links_it(page: Any) -> None:
    if not log_in(page):
        pytest.skip("this dashboard has nobody to choose")
    menu = page.locator(".topbar details.account")
    menu.locator("summary").click()
    assert menu.locator("a[href='/profile']", has_text="Profile settings").count() == 1
    page.goto(URL + "/profile", wait_until="load", timeout=120_000)
    names = [t.strip() for t in page.locator(".setting-row .setting-name").all_inner_texts()]
    assert names == SETTINGS
    assert page.locator("input[name=opens]").count() == 2
    assert page.locator("select[name=time_zone] option").first.inner_text().endswith("(dashboard default)")


def test_profile_settings_offers_a_picture_upload(page: Any) -> None:
    """David, 9 Nov: a person uploads their own picture, shown in place of their initials. The file box has no name, so
    the profile's Save never sends it; choosing a file saves the picture on its own."""
    if not log_in(page):
        pytest.skip("this dashboard has nobody to choose")
    page.goto(URL + "/profile", wait_until="load", timeout=120_000)
    field = page.locator(".picture-field")
    upload = field.locator("input[type=file]")
    assert upload.count() == 1 and upload.get_attribute("name") is None
    assert all(t in (upload.get_attribute("accept") or "") for t in ("image/jpeg", "image/png", "image/webp"))
    assert field.locator("label", has_text="picture").count() == 1
    shown = field.locator(".avatar")
    assert shown.count() == 1   # the picture, or the initials until there is one
    has_picture = shown.evaluate("e => e.tagName") == "IMG"
    assert field.locator("button", has_text="Remove").count() == (1 if has_picture else 0)


def test_a_missing_picture_is_not_found(page: Any) -> None:
    response = page.request.get(URL + "/api/picture?name=" + "Nobody%20At%20All")
    assert response.status == 404
