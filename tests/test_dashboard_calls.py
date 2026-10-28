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
    assert page.locator("table.calls-table tbody tr[data-call-id]").count() <= 10


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


def first_row(page: Any) -> Any:
    return page.locator("table.calls-table tbody tr[data-call-id]").first


def test_the_decide_menu_lists_the_four_decisions_and_the_draft_waits_for_the_worker(page: Any) -> None:
    open_page(page, "/review")
    if page.locator("table.calls-table").count() == 0:
        pytest.skip("nothing is waiting, so the queue has no table")
    menu = first_row(page).locator("details.decide-menu")
    menu.locator("summary").click()
    items = [t.strip() for t in menu.locator(".menu-body button").all_inner_texts()]
    assert items == ["Pursue", "Not relevant", "Submitted", "Dismiss", "Pursue and start the draft"]
    waiting = "Drafting is not set up yet" in menu.locator(".menu-body .hint").inner_text()
    assert menu.locator(".menu-body button", has_text="Pursue and start the draft").is_disabled() == waiting
    page.keyboard.press("Escape")   # closes the menu without deciding
    assert not menu.evaluate("m => m.open")


def test_a_note_button_opens_the_reasons_panel_and_close_hands_focus_back(page: Any) -> None:
    open_page(page, "/review")
    button = page.locator("table.calls-table .note-btn").first
    if button.count() == 0:
        pytest.skip("no waiting call has a judge's reason")
    panel = page.locator(f"[id='{button.get_attribute('data-panel')}']")
    assert panel.is_hidden()
    button.click()
    assert panel.is_visible() and button.get_attribute("aria-expanded") == "true"
    panel.locator(".panel-close").click()
    assert panel.is_hidden()
    assert button.evaluate("b => b === document.activeElement")


def test_a_header_menu_holds_sorts_search_hide_column_and_table_settings(page: Any) -> None:
    open_page(page, "/calls")
    header = page.locator("table.calls-table thead th", has_text="Description")
    header.locator("summary").click()
    body = header.locator(".menu-body")
    assert body.locator("input[type=search][name=desc]").count() == 1
    assert body.get_by_role("button", name="Hide column").count() == 1
    assert body.get_by_role("button", name="Table settings").count() == 1
    page.keyboard.press("Escape")
    due = page.locator("table.calls-table thead th", has_text="Due")
    due.locator("summary").click()
    assert [t.strip() for t in due.locator(".menu-body a").all_inner_texts()][:2] == ["Sort closing soonest first", "Sort closing latest first"]


def test_hide_column_hides_it_until_table_settings_resets(page: Any) -> None:
    open_page(page, "/review")
    if page.locator("table.calls-table").count() == 0:
        pytest.skip("nothing is waiting, so the queue has no table")
    header = page.locator("table.calls-table thead th", has_text="Description")
    header.locator("summary").click()
    header.get_by_role("button", name="Hide column").click()
    page.wait_for_timeout(2000)
    page.reload(wait_until="load")
    hidden = headers(page)
    page.locator(".filter-bar").get_by_role("button", name="Table settings").click()
    page.locator("dialog#table-settings").get_by_role("button", name="Reset to defaults").click()
    page.wait_for_timeout(2000)
    page.reload(wait_until="load")
    assert "Description" not in hidden
    assert "Description" in headers(page)


def test_a_keyword_search_narrows_the_table_and_presses_no_card(page: Any) -> None:
    open_page(page, "/review?desc=zzqq-matches-nothing")
    assert pressed(page) == []
    assert page.locator("table.calls-table").count() == 0


def test_a_top_10_row_on_home_opens_calls_with_that_call_focused(page: Any) -> None:
    open_page(page, "/")
    row = page.locator("section.top-ten tbody tr.row-link").first
    if row.count() == 0:
        pytest.skip("Home has no Top 10 yet")
    row.locator("td.rank").click()
    page.wait_for_url("**/review?view=top10&focus=*", timeout=30_000)
    page.wait_for_timeout(1000)
    focused = page.locator("table.calls-table tbody tr.focused")
    assert focused.count() == 1
    assert focused.evaluate("r => r === document.activeElement")
    call_id = focused.get_attribute("data-call-id")
    assert page.locator(f"[id='reasons-{call_id}']").is_visible()
