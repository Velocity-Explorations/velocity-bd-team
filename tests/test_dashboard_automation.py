"""Automation's six views and the past weekly briefs (PRO-573): six cards in order, Scans' sortable
Started column and Portals filter, and the briefs page's way back to Home and its boards' links.

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


@pytest.fixture()
def page() -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page(viewport={"width": 1440, "height": 900})
        browser.close()


def open_page(page: Any, path: str) -> None:
    page.goto(URL + path, wait_until="load", timeout=120_000)
    page.wait_for_function("!document.querySelector('.loading-page')", timeout=60_000)   # the page has streamed in
    page.wait_for_timeout(300)


def test_automation_has_six_cards_in_order(page: Any) -> None:
    open_page(page, "/requests")
    labels = [t.strip().lower() for t in page.locator(".view-cards .vt-card__label").all_inner_texts()]
    assert labels == ["fit ratings", "agent update requests", "decided requests", "scans", "scan problems", "judges agree"]


def test_the_automation_section_opens_on_fit_ratings(page: Any) -> None:
    """David, 9 Nov: Fit ratings is what shows when Automation opens."""
    open_page(page, "/")
    assert page.locator(".topbar nav a", has_text="Automation").get_attribute("href") == "/fit"


def test_fit_ratings_lists_each_section_with_its_evidence_and_one_rating_pressed(page: Any) -> None:
    open_page(page, "/fit")
    if page.locator(".fit-section").count() == 0:
        pytest.skip("this database has no fit ratings yet")
    assert [t.strip() for t in page.locator(".fit-section h2").all_inner_texts()] == ["Work", "Customer", "Type", "Access", "Keywords", "NAICS"]
    assert page.locator(".fit-scale li").count() == 5
    row = page.locator(".fit-section#work tbody tr").filter(has_text="Software").first
    slider = row.locator("input[type=range].fit-slider")   # David, 9 Nov: a slider in place of five buttons
    assert slider.count() == 1 and (slider.get_attribute("min"), slider.get_attribute("max")) == ("0", "4")
    assert [t.strip() for t in row.locator(".fit-stops li").all_inner_texts()] == ["Never", "Poor", "Neutral", "Good", "Core"]
    assert slider.get_attribute("aria-valuetext") in ("Never", "Poor", "Neutral", "Good", "Core")
    assert row.locator("input[type=hidden][name=rating]").input_value() in ("never", "poor", "neutral", "good", "core")
    assert row.locator(".fit-mix").count() == 2
    # David, 9 Nov: one Calls column, with how many are mostly this work under the count on Work rows
    heads = [t.strip() for t in page.locator(".fit-section#work thead th").all_inner_texts()]
    assert heads[:3] == ["Work", "Rating and note", "Calls"] and "Primary focus of call" not in heads   # David, 9 Nov
    assert re.fullmatch(r"\d+ as primary focus", row.locator("td .fit-focus .meta").inner_text().strip())
    assert page.locator(".fit-section#customer .fit-focus").count() == 0
    # and every column header explains itself on hover or keyboard focus
    for section in ("work", "keyword"):
        for th in page.locator(f".fit-section#{section} thead th").all():
            help_ = th.locator(".th-help")
            assert help_.count() == 1 and (help_.get_attribute("title") or "").strip(), th.inner_text()
            assert help_.get_attribute("tabindex") == "0"
    row.locator(".fit-examples summary").click()
    assert row.locator(".fit-examples li").count() >= 1


def test_a_fit_note_shows_whole_and_saving_it_keeps_the_rating(page: Any) -> None:
    open_page(page, "/fit")
    if page.locator(".fit-section").count() == 0:
        pytest.skip("this database has no fit ratings yet")
    for form in page.locator(".fit-form").all()[:12]:
        note = form.locator("textarea")
        assert note.evaluate("n => n.scrollHeight <= n.clientHeight + 2")   # nothing is cut off
        rating = form.locator("input[type=hidden][name=rating]").input_value()
        slider = form.locator("input[type=range].fit-slider")
        if rating:   # Save note sends the rating the slider holds; Clear is offered only on a rated row
            assert slider.get_attribute("aria-valuetext") == rating.capitalize()
            assert form.locator("button.fit-clear").count() == 1
        else:
            assert slider.get_attribute("aria-valuetext") == "not rated" and form.locator("button.fit-clear").count() == 0
        assert form.locator("button", has_text="Save note").count() == 0   # David, 9 Nov: a note saves as it is typed
        assert note.is_disabled() == (not rating)   # a note needs a rating


def test_fit_ratings_does_not_scroll_sideways_at_a_laptop_width(page: Any) -> None:
    page.set_viewport_size({"width": 1280, "height": 800})
    open_page(page, "/fit")
    assert page.evaluate("document.scrollingElement.scrollWidth - window.innerWidth") <= 0


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
