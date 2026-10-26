"""The filter bar above the table and the column headers' sort and filter controls (PRO-558).

Every control is a link or a GET form, so these tests only read: they never write to the ledger.
Name a serving dashboard in DASHBOARD_TEST_URL; without it they are skipped.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

URL = os.environ.get("DASHBOARD_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_TEST_URL to a running dashboard")


@pytest.fixture()
def page() -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page(viewport={"width": 1440, "height": 900})
        browser.close()


def go(page: Any, action: Any) -> None:
    action()
    page.wait_for_load_state("load")
    page.wait_for_timeout(800)


def test_the_filters_sit_in_a_bar_above_the_table_not_a_side_panel(page: Any) -> None:
    for path in ("/", "/calls"):
        page.goto(URL + path, wait_until="load", timeout=120_000)
        assert page.locator("aside.panel").count() == 0
        bar = page.locator(".filter-bar")
        assert bar.count() == 1 and "Portals" in bar.inner_text() and "Open" in bar.inner_text()


def test_a_header_sorts_and_a_second_click_reverses_it(page: Any) -> None:
    page.goto(URL + "/calls", wait_until="load", timeout=120_000)
    go(page, lambda: page.locator("thead a.th-sort", has_text="Due").click())
    assert "sort=due" in page.url and "dir=" not in page.url
    assert page.locator("thead th[aria-sort=ascending]", has_text="Due").count() == 1
    go(page, lambda: page.locator("thead a.th-sort", has_text="Due").click())
    assert "sort=due" in page.url and "dir=desc" in page.url


def test_a_header_menu_filters_its_column_and_the_bar_keeps_that_filter(page: Any) -> None:
    page.goto(URL + "/calls", wait_until="load", timeout=120_000)
    header = page.locator("thead th", has_text="Claude / Grok")
    header.locator("summary").click()
    go(page, lambda: header.get_by_role("link", name="no", exact=True).click())
    assert "verdict=no" in page.url
    go(page, lambda: page.locator(".filter-bar .segmented a", has_text="Open").click())
    assert "state=open" in page.url and "verdict=no" in page.url


@pytest.mark.parametrize("path", ["/", "/calls"])
def test_the_portals_menu_lists_every_scanned_portal_with_its_call_count(page: Any, path: str) -> None:
    """A portal that scanned but stored nothing still shows, greyed with 0 (PRO-563)."""
    page.goto(URL + path, wait_until="load", timeout=120_000)
    menu = page.locator(".filter-bar details.menu", has_text="Portals")
    menu.locator("summary").click()
    entries = menu.locator("label.check")
    assert entries.count() > 0
    for i in range(entries.count()):
        entry = entries.nth(i)
        count = entry.locator(".count").inner_text().strip()
        assert count.isdigit(), entry.inner_text()
        assert ("no-calls" in (entry.get_attribute("class") or "")) == (count == "0"), entry.inner_text()


def test_the_portals_menu_applies_when_it_closes(page: Any) -> None:
    page.goto(URL + "/", wait_until="load", timeout=120_000)
    page.wait_for_timeout(800)   # the page's script has loaded
    menu = page.locator(".filter-bar details.menu", has_text="Portals")
    menu.locator("summary").click()
    menu.locator("input[type=checkbox]").first.check()
    go(page, lambda: menu.locator("summary").click())
    assert "portal=" in page.url
