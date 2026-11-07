"""Calls' views and columns (PRO-571): seven cards in order, no card pressed when a column filter
matches no view (VC4), the columns in the handoff's order, Top 10 at most ten calls, and the AI
reason folding under the call below 1280px.

These only read, never write to the ledger. Each test starts with no settings cookie, so the default
columns show. Name a serving dashboard in DASHBOARD_TEST_URL; without it they are skipped.
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
    assert headers(page) == ["Call", "Votes", "Summary description", "AI reason", "Due", "Decide"]


def test_all_calls_shows_the_handoffs_columns(page: Any) -> None:
    open_page(page, "/calls")
    if page.locator("table.calls-table").count() == 0:
        pytest.skip("the ledger has no calls")
    assert headers(page) == ["Call", "Filter", "Votes", "Summary description", "AI reason", "Due", "Decide"]
    # The header says what the cells hold, so a summary carries no label of its own.
    assert "summary" not in [t.strip().lower() for t in page.locator("table.calls-table .desc-label").all_inner_texts()]


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
    assert not page.locator("table.calls-table thead th", has_text="Summary description").is_visible()


def first_row(page: Any) -> Any:
    return page.locator("table.calls-table tbody tr[data-call-id]").first


def test_needs_review_shows_the_fit_score_with_its_reasons_and_opens_best_fit_first(page: Any) -> None:
    open_page(page, "/review")
    badges = page.locator("table.calls-table tbody td.votes-cell .judge.fit .badge")
    if badges.count() == 0:
        pytest.skip("no call on this page has a fit score yet")
    assert badges.first.get_attribute("title")   # what the score rests on
    scores = [int(text.split()[0]) for text in badges.all_inner_texts() if text.split()[0].isdigit()]
    assert scores == sorted(scores, reverse=True)


def test_the_decide_menu_lists_the_four_decisions_and_the_draft_waits_for_the_worker(page: Any) -> None:
    open_page(page, "/review")
    if page.locator("table.calls-table").count() == 0:
        pytest.skip("nothing is waiting, so the queue has no table")
    menu = first_row(page).locator("details.decide-menu")
    menu.locator(":scope > summary").click()
    items = [t.strip() for t in menu.locator(".menu-body > button, .menu-body > details > summary").all_inner_texts()]
    assert items == ["Pursue", "Not relevant", "Submitted", "Dismiss", "Pursue and start the draft"]
    waiting = "Drafting is not set up yet" in menu.locator(":scope > .menu-body > .hint").inner_text()
    assert menu.locator(":scope > .menu-body > button", has_text="Pursue and start the draft").is_disabled() == waiting
    page.keyboard.press("Escape")   # closes the menu without deciding
    assert not menu.evaluate("m => m.open")


def test_not_relevant_on_a_call_claude_liked_asks_why(page: Any) -> None:
    """David, 5 Nov: the reason a Not relevant call carries is what the judges learn from (review/feedback.py)."""
    open_page(page, "/review")
    if page.locator("table.calls-table").count() == 0:
        pytest.skip("nothing is waiting, so the queue has no table")
    menu = first_row(page).locator("details.decide-menu")
    menu.locator(":scope > summary").click()
    reasons = menu.locator("details.reason-menu")
    assert reasons.count() == 1
    reasons.locator("summary").click()
    picks = reasons.locator(".reason-body button")
    assert [t.strip() for t in picks.all_inner_texts()] == [
        "Mostly hardware", "Staffing or IT support", "Wrong customer or eligibility", "Too broad, no clear fit",
        "Award or sole-source notice", "Save another reason"]
    assert picks.first.get_attribute("value") == "not_relevant:hardware"
    assert reasons.locator("input[name=reason_text]").is_visible()
    assert menu.evaluate("m => m.open")   # the reasons open inside the Decide menu, which stays open
    page.keyboard.press("Escape")


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
    header = page.locator("table.calls-table thead th", has_text="Summary description")
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
    header = page.locator("table.calls-table thead th", has_text="Summary description")
    header.locator("summary").click()
    header.get_by_role("button", name="Hide column").click()
    page.wait_for_timeout(2000)
    page.reload(wait_until="load")
    hidden = headers(page)
    page.locator(".filter-bar").get_by_role("button", name="Table settings").click()
    page.locator("dialog#table-settings").get_by_role("button", name="Reset to defaults").click()
    page.wait_for_timeout(2000)
    page.reload(wait_until="load")
    assert "Summary description" not in hidden
    assert "Summary description" in headers(page)


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


PAGE = 100   # calls a page on All calls and Needs review (dashboard/lib/filters.ts PAGE_SIZE)


def call_rows(page: Any) -> int:
    return page.locator("table.calls-table tbody tr[data-call-id]").count()


def listed(page: Any) -> int:
    """How many calls the bar's count says the view holds: "Showing 100 of 412", "Showing 101 to 200 of 412", "12 calls"."""
    text = page.locator(".bar-count").first.inner_text()
    found = re.search(r"of (\d+)", text) or re.match(r"\s*(\d+) call", text)
    assert found, text
    return int(found.group(1))


@pytest.mark.parametrize("path", ["/calls", "/review"])
def test_a_table_shows_a_page_of_calls_with_links_either_side(page: Any, path: str) -> None:
    open_page(page, path)
    if page.locator("table.calls-table").count() == 0 or listed(page) <= PAGE:
        pytest.skip("one page holds every call")
    assert call_rows(page) == PAGE
    assert page.locator("nav.pager a[rel=prev]").count() == 0
    page.locator("nav.pager a[rel=next]").click()
    page.wait_for_url(re.compile(r"[?&]page=2"), timeout=60_000)
    assert 0 < call_rows(page) <= PAGE
    assert f"{PAGE + 1} to " in page.locator(".bar-count").first.inner_text()
    assert page.locator("nav.pager a[rel=prev]").count() == 1


def test_a_page_past_the_last_opens_the_last(page: Any) -> None:
    open_page(page, "/calls?page=9999")
    page.wait_for_url(lambda url: "page=9999" not in url, timeout=60_000)   # the page has streamed, so the browser redirects
    if page.locator("table.calls-table").count() == 0 and "page=" not in page.url:
        pytest.skip("the ledger has no calls")
    assert "page=9999" not in page.url
    assert call_rows(page) > 0
    assert page.locator("nav.pager a[rel=next]").count() == 0


@pytest.mark.parametrize("path", ["/calls", "/review"])
def test_a_table_page_stays_light(page: Any, path: str) -> None:
    # 200 rows a page made All calls 4 MB of HTML, two to three seconds on the server and more in the browser;
    # 100 make about 2 MB.
    response = page.request.get(URL + path)
    assert response.ok
    assert len(response.body()) < 3_000_000
