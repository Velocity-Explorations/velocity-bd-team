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
    "/proposals?view=closing": "Proposals",
    "/proposals?view=drafting": "Proposals",
    "/proposals/submitted": "Proposals",
    "/proposals/results": "Proposals",
    "/requests": "Automation",
    "/requests?view=decided": "Automation",
    "/runs": "Automation",
    "/runs?view=problems": "Automation",
    "/judges": "Automation",
    "/fit": "Automation",
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
    "/fit": "Fit ratings",
}
COUNT_LABEL = re.compile(r"^\d+ (waiting for you|to draft, ready for you or overdue|requests? waiting)$")


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
    # Home records only the Top 10's decisions (H5, David 5 Nov)
    assert page.locator("main form").count() == page.locator("section.top-ten form.decide-form").count()
    top = page.locator("section.top-ten")
    assert top.count() == 1
    panels = top.locator("[role=tabpanel]")
    assert panels.count() == 2   # the calls, and the umbrellas and announcements to watch (David, 7 Nov)
    for i in range(2):
        assert panels.nth(i).locator("table").count() + panels.nth(i).locator(".empty").count() == 1
    assert page.locator("main a[href='/brief']").count() >= 1


def open_tab(page: Any, key: str) -> None:
    """Click a Top 10 tab, again if the page had not finished starting when the first click landed."""
    for _ in range(3):
        page.locator(f"#top-tab-{key}").click()
        try:
            page.wait_for_function(f"!document.querySelector('#top-panel-{key}').hidden", timeout=5_000)
            return
        except Exception:
            continue
    raise AssertionError(f"the {key} tab did not open")


def test_home_keeps_its_two_top_10s_in_tabs_and_a_link_opens_either(page: Any) -> None:
    """David, 7 Nov: the calls to respond to now on one tab, the umbrellas and announcements to watch on the next."""
    open_page(page, "/")
    tabs = page.locator("section.top-ten [role=tab]")
    assert [re.sub(r"\s*\d+$", "", t).strip() for t in tabs.all_inner_texts()] == ["Top 10 calls", "Top 10 to watch"]
    assert tabs.first.get_attribute("aria-selected") == "true"
    assert page.locator("#top-panel-calls").is_visible() and page.locator("#top-panel-watch").is_hidden()
    open_tab(page, "watch")
    assert page.locator("#top-panel-calls").is_hidden()
    assert page.url.endswith("/?top=watch")
    page.keyboard.press("ArrowLeft")   # the arrow keys move between the tabs
    page.wait_for_function("!document.querySelector('#top-panel-calls').hidden", timeout=5_000)
    assert "top=" not in page.url
    open_page(page, "/?top=watch")
    assert page.locator("#top-tab-watch").get_attribute("aria-selected") == "true"
    assert page.locator("#top-panel-watch").is_visible()
    rows = page.locator("#top-panel-watch tbody tr")
    if rows.count():
        assert rows.first.locator(".badge", has_text=re.compile(r"^(umbrella|announcement)$")).count() == 1
        assert rows.first.get_attribute("data-href") is None   # Calls' Top 10 does not hold them


def test_home_top_10_heads_its_summaries_summary_description(page: Any) -> None:
    open_page(page, "/")
    table = page.locator("section.top-ten table")
    if table.count() == 0:
        pytest.skip("there is no Top 10 yet")
    heads = [t.strip().lower() for t in table.locator("thead th").all_inner_texts()]
    assert "summary description" in heads and "description" not in heads
    assert "summary" not in [t.strip().lower() for t in table.locator(".desc-label").all_inner_texts()]


@pytest.mark.parametrize("path", ["/", "/review", "/calls"])
def test_a_page_streams_its_loading_screen_before_its_content(path: str) -> None:
    """A page takes a second or so to read the ledger; its loading screen goes out first, so a click shows at once."""
    import urllib.request

    with urllib.request.urlopen(URL + path, timeout=120) as response:
        html = response.read().decode("utf-8", "replace")
    assert html.index('class="loading-page"') < html.index("<main>")


def test_each_top_10_call_on_home_can_be_decided_there(page: Any) -> None:
    """David, 5 Nov: a Top 10 call is decided from Home, without going to Calls first."""
    open_page(page, "/")
    rows = page.locator("#top-panel-calls tbody tr")
    if rows.count() == 0:
        pytest.skip("there is no Top 10 yet")
    assert "decide" in [t.strip().lower() for t in page.locator("#top-panel-calls thead th").all_inner_texts()]
    assert page.locator("#top-panel-calls tbody td.decide").count() == rows.count()
    first = rows.first
    first.locator("details.decide-menu > summary").click()
    items = [t.strip() for t in first.locator("details.decide-menu > .menu-body > button, details.decide-menu > .menu-body > details > summary").all_inner_texts()]
    assert items[:4] == ["Pursue", "Not relevant", "Submitted", "Dismiss"]
    assert page.url.rstrip("/") == URL   # opening the menu stays on Home; the row's link is not followed
    assert first.locator("input[name=return_to]").get_attribute("value") == "/"
    page.keyboard.press("Escape")   # closes the menu without deciding


def test_a_not_relevant_decision_wears_the_red_of_a_judges_no(page: Any) -> None:
    """David, 5 Nov: the team's not relevant chip looks like the judges' no chip."""
    open_page(page, "/")
    chips = page.locator("section.top-ten tbody .badge", has_text="not relevant")
    if chips.count() == 0:
        pytest.skip("no Top 10 call is marked not relevant")
    no = page.locator("section.top-ten tbody .badge", has_text=re.compile(r"^no$"))
    assert "tone-bad" in (chips.first.get_attribute("class") or "")
    if no.count():
        assert chips.first.get_attribute("class") == no.first.get_attribute("class")


# ---------------------------------------------------------------------- Ask Grok (David, 7 Nov 2026)

def open_ask(page: Any) -> Any:
    """Open Ask Grok from the top bar, again if the page had not finished starting; skip before migration 016."""
    button = page.locator("header.topbar button.ask-button")
    if button.count() == 0:
        pytest.skip("Ask Grok is not set up here (migration 016)")
    for _ in range(3):
        button.click()
        try:
            page.wait_for_function("document.querySelector('#ask-grok').open", timeout=5_000)
            return page.locator("dialog#ask-grok")
        except Exception:
            continue
    raise AssertionError("Ask Grok did not open")


def test_ask_grok_opens_beside_the_page_and_closes_back_to_its_button(page: Any) -> None:
    open_page(page, "/calls")
    panel = open_ask(page)
    assert panel.locator("h2").inner_text().strip() == "Ask Grok"
    assert page.locator("main").is_visible() and page.locator("header.topbar nav a").first.is_enabled()
    box = panel.locator("textarea")
    if box.is_disabled():   # nobody is logged in on this test server
        assert "Log in" in (box.get_attribute("placeholder") or "")
        assert panel.locator("button[type=submit]").is_disabled()
    page.keyboard.press("Escape")
    page.wait_for_function("!document.querySelector('#ask-grok').open", timeout=5_000)
    assert page.evaluate("document.activeElement && document.activeElement.classList.contains('ask-button')")


def test_nobody_can_read_a_thread_without_logging_in(page: Any) -> None:
    import urllib.error
    import urllib.request

    open_page(page, "/")
    if page.locator("header.topbar button.ask-button").count() == 0:
        pytest.skip("Ask Grok is not set up here (migration 016)")
    try:
        with urllib.request.urlopen(URL + "/api/ask", timeout=60) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
    assert status == 401


@pytest.mark.skipif(os.environ.get("ASK_TESTS") != "1", reason="sends a real question to Grok and the live ledger: ASK_TESTS=1")
def test_a_question_asked_in_the_panel_gets_grok_s_answer(page: Any) -> None:
    open_page(page, "/review")
    menu = page.locator(".topbar details.account")
    menu.locator("summary").click()
    names = menu.locator("form.choose-viewer button[name=viewer]")
    if names.count() == 0:
        pytest.skip("nobody to log in as")
    names.first.click()
    page.wait_for_timeout(2000)
    panel = open_ask(page)
    panel.locator("button.ask-new").click()
    panel.locator("textarea").fill("In one line: how many open calls are umbrellas this week?")
    panel.locator("textarea").press("Enter")
    page.wait_for_selector("#ask-grok .ask-exchange[data-state=done], #ask-grok .ask-exchange[data-state=failed]", timeout=150_000)
    last = panel.locator(".ask-exchange").last
    assert last.get_attribute("data-state") == "done", last.inner_text()
    assert last.locator(".ask-answer").inner_text().strip()
    assert "grok-4.7" in last.locator(".meta").last.inner_text()
