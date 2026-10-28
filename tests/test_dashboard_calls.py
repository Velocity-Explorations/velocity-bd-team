"""Calls' views and columns (PRO-571): seven cards in order, no card pressed when a column filter
matches no view (VC4), the columns in the handoff's order, Top 10 at most ten calls, and the AI
reason folding under the call below 1280px.

These only read, never write to the ledger. Each test starts with no settings cookie, so the default
columns show. Name a serving dashboard in DASHBOARD_TEST_URL; without it they are skipped.
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


def headers(page: Any) -> list[str]:
    return [t.strip() for t in page.locator("table.calls-table thead th").all_inner_texts()]


def pressed(page: Any) -> list[str]:
    return [t.strip().lower() for t in page.locator(".view-cards .vt-card[aria-current=page] .vt-card__label").all_inner_texts()]


def test_calls_has_seven_cards_in_order(page: Any) -> None:
    open_page(page, "/review")
    labels = [t.strip().lower() for t in page.locator(".view-cards .vt-card__label").all_inner_texts()]
    assert labels == ["needs review", "top 10", "due soon", "judges agree", "judges disagree", "new this week", "all calls"]


def test_a_column_filter_that_matches_no_view_leaves_no_card_pressed(page: Any) -> None:
    open_page(page, "/review?verdict=yes")
    assert pressed(page) == []
    open_page(page, "/review?judges=agree")
    assert pressed(page) == ["judges agree"]
    open_page(page, "/calls?status=pursue")
    assert pressed(page) == []


def test_the_queue_shows_the_handoffs_columns(page: Any) -> None:
    open_page(page, "/review")
    if page.locator("table.calls-table").count() == 0:
        pytest.skip("nothing is waiting, so the queue has no table")
    assert headers(page) == ["Call", "Votes", "Description", "AI reason", "Due", "Decide"]


def test_all_calls_shows_the_handoffs_columns(page: Any) -> None:
    open_page(page, "/calls")
    if page.locator("table.calls-table").count() == 0:
        pytest.skip("the ledger has no calls")
    assert headers(page) == ["Call", "Filter", "Votes", "Description", "AI reason", "Due", "Decide"]


def test_top_10_lists_at_most_ten_calls(page: Any) -> None:
    open_page(page, "/review?view=top10")
    assert page.locator("table.calls-table tbody tr").count() <= 10


def test_below_1280px_the_reason_folds_under_the_call(page: Any) -> None:
    open_page(page, "/review")
    if page.locator("table.calls-table").count() == 0:
        pytest.skip("nothing is waiting, so the queue has no table")
    folded = page.locator("table.calls-table tbody tr").first.locator(".folded-reason")
    column = page.locator("table.calls-table thead th", has_text="AI reason")
    page.set_viewport_size({"width": 1280, "height": 900})
    assert column.is_visible() and not folded.is_visible()
    page.set_viewport_size({"width": 1279, "height": 900})
    assert not column.is_visible() and folded.is_visible()
    assert not page.locator("table.calls-table thead th", has_text="Description").is_visible()
