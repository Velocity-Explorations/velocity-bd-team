"""The four sections, their view cards and Home (PRO-570): the bar marks the open section and labels
its counts, every old address opens its view, each section opens on a row of view cards, switching
cards keeps the bar's filters, and Home shows five link cards and the Top 10.

These only read, never write to the ledger. Name a serving dashboard in DASHBOARD_TEST_URL; without it
they are skipped.
"""
from __future__ import annotations

import os
import re
from typing import Any

import pytest

URL = os.environ.get("DASHBOARD_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_TEST_URL to a running dashboard")

SECTION_OF = {
    "/": "Home",
    "/brief": "Home",
    "/review": "Calls",
    "/review?view=due-soon": "Calls",
    "/review?view=top10": "Calls",
    "/review?view=judges-agree": "Calls",
    "/review?view=judges-disagree": "Calls",
    "/review?view=new": "Calls",
    "/calls": "Calls",
    "/proposals": "Proposals",
    "/requests": "Automation",
    "/requests?view=decided": "Automation",
    "/runs": "Automation",
    "/runs?view=problems": "Automation",
    "/judges": "Automation",
}
CARD_PAGES = {
    "/review": "Needs review",
    "/review?view=due-soon": "Due soon",
    "/review?view=top10": "Top 10",
    "/review?view=judges-agree": "Judges agree",
    "/review?view=judges-disagree": "Judges disagree",
    "/review?view=new": "New this week",
    "/calls": "All calls",
    "/requests": "Agent update requests",
    "/requests?view=decided": "Decided requests",
    "/runs": "Scans",
    "/runs?view=problems": "Scan problems",
    "/judges": "Judges agree",
}
COUNT_LABEL = re.compile(r"^\d+ (waiting for you|to draft or ready for you|requests? waiting)$")


@pytest.fixture(scope="module")
def page() -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page(viewport={"width": 1440, "height": 900})
        browser.close()


def open_page(page: Any, path: str) -> Any:
    response = page.goto(URL + path, wait_until="load", timeout=120_000)
    page.wait_for_timeout(300)
    return response


@pytest.mark.parametrize("path", list(SECTION_OF))
def test_every_address_opens_and_the_bar_marks_its_section(page: Any, path: str) -> None:
    response = open_page(page, path)
    assert response is not None and response.status == 200
    links = page.locator(".topbar nav a")
    assert [re.sub(r"\d+", "", t).strip() for t in links.all_inner_texts()] == ["Home", "Calls", "Proposals", "Automation"]
    current = page.locator(".topbar nav a[aria-current=page]")
    assert current.count() == 1
    assert re.sub(r"\d+", "", current.inner_text()).strip() == SECTION_OF[path]


def test_the_counts_say_what_they_count(page: Any) -> None:
    open_page(page, "/")
    for chip in page.locator(".topbar .count-chip").all():
        assert COUNT_LABEL.match(chip.get_attribute("aria-label") or ""), chip.get_attribute("aria-label")
    assert page.locator(".topbar .brand").inner_text().strip().upper() == "BD TEAM"


@pytest.mark.parametrize("path", list(CARD_PAGES))
def test_each_section_opens_on_view_cards_with_its_view_pressed(page: Any, path: str) -> None:
    open_page(page, path)
    assert page.locator(".page-head").count() == 0
    cards = page.locator(".view-cards .vt-card")
    assert cards.count() >= 3
    pressed = page.locator(".view-cards .vt-card[aria-current=page]")
    assert pressed.count() == 1
    assert pressed.locator(".vt-card__label").inner_text().strip().lower() == CARD_PAGES[path].lower()


def test_switching_cards_keeps_the_bar_filters_and_drops_the_sort(page: Any) -> None:
    open_page(page, "/review?state=open&sort=due&verdict=yes")
    href = page.locator(".view-cards .vt-card", has=page.locator(".vt-card__label", has_text="All calls")).get_attribute("href")
    assert href == "/calls?state=open"


def test_home_shows_five_link_cards_then_the_top_10(page: Any) -> None:
    open_page(page, "/")
    labels = [t.strip().lower() for t in page.locator(".view-cards .vt-card .vt-card__label").all_inner_texts()]
    assert labels == ["needs review", "due soon", "agent update requests", "proposals to draft", "submitted and waiting"]
    assert page.locator(".view-cards .vt-card[aria-current]").count() == 0
    assert page.locator("main form").count() == 0   # Home records nothing (H5)
    top = page.locator("section.top-ten")
    assert top.count() == 1
    assert top.locator("table").count() == 1 or top.locator(".empty").count() == 1
    assert page.locator("main a[href='/brief']").count() >= 1
