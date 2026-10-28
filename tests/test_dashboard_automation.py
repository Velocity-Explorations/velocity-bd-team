"""Automation's five views and the past weekly briefs (PRO-573): five cards in order, Scans' sortable
Started column and Portals filter, and the briefs page's way back to Home and its boards' links.

These only read, never write to the ledger. Name a serving dashboard in DASHBOARD_TEST_URL; without it
they are skipped.
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


def open_page(page: Any, path: str) -> None:
    page.goto(URL + path, wait_until="load", timeout=120_000)
    page.wait_for_timeout(300)


def test_automation_has_five_cards_in_order(page: Any) -> None:
    open_page(page, "/requests")
    labels = [t.strip().lower() for t in page.locator(".view-cards .vt-card__label").all_inner_texts()]
    assert labels == ["agent update requests", "decided requests", "scans", "scan problems", "judges agree"]


def test_scans_sort_by_started_newest_first_and_flip(page: Any) -> None:
    open_page(page, "/runs")
    if page.locator("table").count() == 0:
        pytest.skip("no runs recorded")
    started = page.locator("thead th", has_text="Started")
    assert started.get_attribute("aria-sort") == "descending"
    started.locator("a.th-sort").click()
    page.wait_for_url("**/runs?dir=asc", timeout=30_000)
    assert page.locator("thead th", has_text="Started").get_attribute("aria-sort") == "ascending"


def test_scans_have_a_portals_filter(page: Any) -> None:
    open_page(page, "/runs?view=problems")
    menu = page.locator(".filter-bar details.menu", has_text="Portals")
    assert menu.count() == 1
    menu.locator("summary").click()
    assert menu.locator("input[type=checkbox][name=portal]").count() > 0


def test_the_briefs_page_leads_back_home_and_its_boards_link_their_calls(page: Any) -> None:
    open_page(page, "/brief")
    assert page.locator("nav.breadcrumb a[href='/']").count() == 1
    for href in page.locator(".board-card a.content-card__label").evaluate_all("els => els.map(e => e.getAttribute('href'))"):
        assert href.startswith("/calls?portal="), href
