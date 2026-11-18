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
    "/review?view=unsure": "Calls",
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
    "/review?view=unsure": "Unsure",
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
    # Home records only the Top 10's decisions (H5, David 5 Nov) and, since 18 Nov 2026, its pick ratings (Task 5, migration 022)
    assert page.locator("main form").count() == (page.locator("section.top-ten form.decide-form").count()
                                                 + page.locator("section.top-ten form.pick-form").count())
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
    assert items[:5] == ["Pursue", "Not relevant", "Unsure", "Submitted", "Dismiss"]   # Unsure since 16 Nov 2026
    assert page.url.rstrip("/") == URL   # opening the menu stays on Home; the row's link is not followed
    assert first.locator("form.decide-form input[name=return_to]").get_attribute("value") == "/"
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

ASK_OPEN = "(() => { const p = document.querySelector('#ask-grok'); return !!p && !p.hidden; })()"


def open_ask(page: Any) -> Any:
    """Open Ask Grok from the top bar, again if the page had not finished starting; skip before migration 016."""
    button = page.locator("header.topbar button.ask-button")
    if button.count() == 0:
        pytest.skip("Ask Grok is not set up here (migration 016)")
    if page.evaluate(ASK_OPEN):
        return page.locator("aside#ask-grok")
    for _ in range(3):
        button.click()
        try:
            page.wait_for_function(ASK_OPEN, timeout=5_000)
            return page.locator("aside#ask-grok")
        except Exception:
            continue
    raise AssertionError("Ask Grok did not open")


def close_ask(page: Any) -> None:
    """Close Ask Grok with its own button, so the next test starts with it closed (it stays open from page to page)."""
    if page.evaluate(ASK_OPEN):
        page.locator("#ask-grok button.ask-close").click()
        page.wait_for_function(f"!{ASK_OPEN}", timeout=5_000)


def box_of(page: Any, selector: str) -> dict[str, float]:
    return page.evaluate(f"(() => {{ const r = document.querySelector({selector!r}).getBoundingClientRect(); "
                         "return {left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width}; })()")


def test_ask_grok_docks_beside_the_page_and_closes_back_to_its_button(page: Any) -> None:
    """David, 16 Nov 2026: the panel takes a docked area at the right, and the page narrows beside it, nothing under it."""
    open_page(page, "/calls")
    width = page.viewport_size["width"]
    try:
        panel = open_ask(page)
        assert panel.locator("h2").inner_text().strip() == "Ask Grok"
        dock = box_of(page, "#ask-grok")
        assert dock["top"] == 0 and abs(dock["right"] - width) < 1 and 320 <= dock["width"] <= 480
        assert box_of(page, "main")["right"] <= dock["left"] + 0.5
        assert box_of(page, "header.topbar")["right"] <= dock["left"] + 0.5
        assert page.evaluate("document.documentElement.scrollWidth") <= width   # no sideways scroll
        if box_of(page, "main")["right"] < 1024 and page.locator(".table-wrap").count():
            # the page beside the panel is under 1024px, so a wide table scrolls sideways rather than losing its edge
            assert page.evaluate("getComputedStyle(document.querySelector('.table-wrap')).overflowX") == "auto"
        assert page.locator("header.topbar nav a").first.is_enabled()
        box = panel.locator("textarea")
        if box.is_disabled():   # nobody is logged in on this test server
            assert "Log in" in (box.get_attribute("placeholder") or "")
            assert panel.locator("button[type=submit]").is_disabled()
        panel.locator("button.ask-close").focus()
        page.keyboard.press("Escape")
        page.wait_for_function(f"!{ASK_OPEN}", timeout=5_000)
        assert page.evaluate("document.activeElement && document.activeElement.classList.contains('ask-button')")
        assert page.locator("header.topbar button.ask-button").get_attribute("aria-expanded") == "false"
        assert box_of(page, "main")["right"] > dock["left"] + 100   # the page takes the whole width again
    finally:
        close_ask(page)


def test_escape_on_the_page_leaves_ask_grok_open(page: Any) -> None:
    """Escape closes the panel only from inside it: on the page it closes a menu or a tooltip and nothing more."""
    open_page(page, "/calls")
    try:
        open_ask(page)
        assert page.locator("header.topbar button.ask-button").get_attribute("aria-expanded") == "true"
        page.evaluate("document.activeElement && document.activeElement.blur()")
        page.keyboard.press("Escape")
        page.wait_for_timeout(300)
        assert page.evaluate(ASK_OPEN)
    finally:
        close_ask(page)


def test_ask_grok_stays_open_from_page_to_page_and_across_a_reload(page: Any) -> None:
    """David, 16 Nov 2026: changing page keeps the panel open and in place; it is the same panel, not a new one."""
    open_page(page, "/calls")
    try:
        open_ask(page)
        page.evaluate("window.__askPanel = document.querySelector('#ask-grok')")
        page.locator("header.topbar nav a", has_text="Proposals").click()
        page.wait_for_url(re.compile(r"/proposals"), timeout=60_000)
        page.wait_for_selector("header.topbar nav a[aria-current=page]:has-text('Proposals')", timeout=60_000)
        assert page.evaluate(ASK_OPEN)
        assert page.evaluate("window.__askPanel === document.querySelector('#ask-grok')")   # never closed and rebuilt
        assert box_of(page, "main")["right"] <= box_of(page, "#ask-grok")["left"] + 0.5
        open_page(page, "/runs")   # a full page load: the panel opens where it was, already docked
        assert page.evaluate(ASK_OPEN)
        assert box_of(page, "main")["right"] <= box_of(page, "#ask-grok")["left"] + 0.5
        assert page.locator("header.topbar button.ask-button").get_attribute("aria-expanded") == "true"
        close_ask(page)
        open_page(page, "/runs")
        assert not page.evaluate(ASK_OPEN)
        assert box_of(page, "main")["right"] > page.viewport_size["width"] - 100
    finally:
        close_ask(page)


def test_on_a_narrow_window_ask_grok_lies_over_the_page(page: Any) -> None:
    """Below 960 px there is no room beside the page, so the panel lies over it as before."""
    page.set_viewport_size({"width": 800, "height": 900})
    try:
        open_page(page, "/calls")
        open_ask(page)
        dock = box_of(page, "#ask-grok")
        assert dock["width"] <= 460
        assert box_of(page, "main")["right"] > dock["left"]   # the page keeps its width under the panel
        assert page.locator("#ask-grok .ask-resize").is_hidden()   # nothing to resize against
    finally:
        close_ask(page)
        page.set_viewport_size({"width": 1440, "height": 900})


def test_ask_grok_s_width_is_dragged_kept_and_reset(page: Any) -> None:
    """David, 16 Nov 2026: dragging the panel's left edge widens or narrows it, and this browser keeps the width."""
    open_page(page, "/calls")
    try:
        open_ask(page)
        start = box_of(page, "#ask-grok")
        handle = page.locator("#ask-grok .ask-resize")
        assert handle.get_attribute("role") == "separator" and handle.get_attribute("aria-orientation") == "vertical"
        edge = box_of(page, "#ask-grok .ask-resize")
        x, y = (edge["left"] + edge["right"]) / 2, (edge["top"] + edge["bottom"]) / 2
        page.mouse.move(x, y)
        page.mouse.down()
        page.mouse.move(x - 150, y, steps=6)
        page.mouse.up()
        page.wait_for_timeout(200)
        wide = box_of(page, "#ask-grok")
        assert abs(wide["width"] - (start["width"] + 150)) <= 2
        assert box_of(page, "main")["right"] <= wide["left"] + 0.5
        assert handle.get_attribute("aria-valuenow") == str(round(wide["width"]))
        # the page beside it is now under 1024px, so a wide table scrolls sideways
        assert page.evaluate("getComputedStyle(document.querySelector('.table-wrap')).overflowX") == "auto"
        open_page(page, "/calls")   # kept across a reload, from the first paint
        assert abs(box_of(page, "#ask-grok")["width"] - wide["width"]) <= 1
        handle.focus()
        page.keyboard.press("ArrowRight")   # the arrow keys move the edge: right narrows the panel
        page.wait_for_timeout(200)
        assert abs(box_of(page, "#ask-grok")["width"] - (wide["width"] - 24)) <= 1
        handle.dblclick()   # back to the default width
        page.wait_for_timeout(200)
        assert abs(box_of(page, "#ask-grok")["width"] - start["width"]) <= 1
        assert "ask_width=" not in page.evaluate("document.cookie")
    finally:
        page.evaluate("document.cookie = 'ask_width=; path=/; max-age=0'")
        close_ask(page)


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
    close_ask(page)


def test_the_top_bar_draws_its_theme_behind_everything_in_it(page: Any) -> None:
    """David, 9 Nov 2026: the bar's animation is its first child, under every label, badge, the yellow underline, Ask
    Grok and the account button, and clipped to the bar so menus are not. Nobody has chosen here, so it is Deep field."""
    open_page(page, "/review")
    bar = page.locator("header.topbar")
    fx = bar.locator(":scope > .topbar-fx")
    assert fx.count() == 1 and fx.evaluate("e => e === e.parentElement.firstElementChild")
    assert fx.get_attribute("aria-hidden") == "true"
    assert "topbar-deep" in (fx.get_attribute("class") or "")
    assert fx.locator(".topbar-deep-stars").count() == 3
    style = fx.evaluate("e => { const s = getComputedStyle(e); return [s.position, s.zIndex, s.overflow, s.pointerEvents]; }")
    assert style == ["absolute", "-1", "hidden", "none"]
    assert bar.evaluate("e => { const s = getComputedStyle(e); return [s.isolation, s.overflow]; }") == ["isolate", "visible"]
    for z in bar.locator(":scope > :not(.topbar-fx), nav a, .count-chip").evaluate_all("els => els.map(e => getComputedStyle(e).zIndex)"):
        assert z in ("auto", "0") or int(z) >= 0, z   # nothing in the bar sits below the animation
    # the token the theme paints with is the theme's own ink, not the fallback
    assert bar.evaluate("e => getComputedStyle(e).getPropertyValue('--fx-ink').trim()") == bar.evaluate(
        "e => getComputedStyle(e).getPropertyValue('--ink').trim()")


def test_every_bar_theme_keeps_its_timing_through_the_build(page: Any) -> None:
    """9 Nov 2026: the build's CSS minifier once turned Ground drift's nameless animation shorthand into
    `animation: none`, so its pools never moved. Each theme's moving parts, as the built stylesheet styles them."""
    open_page(page, "/review")
    timing = page.evaluate("""() => {
      const probe = (cls, vars) => {
        const el = document.createElement('div');
        el.className = cls;
        Object.entries(vars).forEach(([k, v]) => el.style.setProperty(k, v));
        document.querySelector('header.topbar .topbar-fx').appendChild(el);
        const s = getComputedStyle(el);
        const out = [s.animationName, s.animationDuration, s.animationIterationCount, s.animationDirection];
        el.remove();
        return out;
      };
      return {
        drift_a: probe('topbar-drift-track topbar-drift-a', {}),
        drift_b: probe('topbar-drift-track topbar-drift-b', {}),
        stars: probe('topbar-deep-stars', { '--dur': '90s', '--tile': '320px' }),
        planets: probe('topbar-deep-planets', { '--dur': '533s', '--tile': '1600px' }),
        moon: probe('topbar-deep-moon', { '--dur': '20s', '--delay': '-3s', '--way': 'reverse' }),
        far_moon: probe('topbar-deep-moon topbar-deep-moon-back', { '--dur': '20s', '--delay': '-3s', '--way': 'normal' }),
        gas: probe('topbar-deep-haze', { '--swirl': '140s', '--breath': '24s', '--delay': '-9s', '--way': 'reverse' }),
      };
    }""")
    assert timing["drift_a"] == ["topbar-drift-a", "30s", "infinite", "alternate"]
    assert timing["drift_b"] == ["topbar-drift-b", "30s", "infinite", "alternate"]
    assert timing["stars"] == ["topbar-deep-drift", "90s", "infinite", "normal"]
    assert timing["planets"] == ["topbar-deep-drift", "533s", "infinite", "normal"]
    assert timing["moon"] == ["topbar-deep-orbit, topbar-deep-near", "20s", "infinite", "reverse"]
    assert timing["far_moon"] == ["topbar-deep-orbit, topbar-deep-far", "20s", "infinite", "normal"]
    assert timing["gas"] == ["topbar-deep-swirl, topbar-deep-breathe", "140s, 24s", "infinite", "reverse, alternate"]


PLANETS = """() => [...document.querySelectorAll('header.topbar .topbar-deep-planets .topbar-deep-planet')].map(e =>
  [e.style.left, e.style.top, e.dataset.kind, e.dataset.ring || '', e.dataset.moons || '', e.dataset.haze !== undefined])"""


def wait_for_planets(page: Any) -> None:
    page.wait_for_selector("header.topbar .topbar-deep-planets .topbar-deep-planet", state="attached", timeout=10_000)


def test_deep_field_draws_planets_over_the_stars_and_under_the_craft(page: Any) -> None:
    """David, 10 Nov 2026: planets of random size, kind and place, some with rings, gas or moons, drift behind the bar.
    Each is drawn twice a loop apart, the loop longer than the bar, and no part of one is brighter than 20% ink."""
    open_page(page, "/review")
    wait_for_planets(page)
    fx = page.locator("header.topbar > .topbar-deep")
    order = fx.evaluate("e => [...e.children].map(c => c.className)")
    assert order[:3] == ["topbar-deep-stars"] * 3 and order[3] == "topbar-deep-planets", order
    planets = page.evaluate(PLANETS)
    assert len(planets) >= 2 and len(planets) % 2 == 0
    assert len({p[2] for p in planets}) == len(planets) // 2   # each kind once a sky, drawn twice
    belt = fx.locator(".topbar-deep-planets")
    loop = int(belt.get_attribute("data-loop") or 0)
    assert loop >= fx.evaluate("e => e.clientWidth")
    assert belt.evaluate("e => [getComputedStyle(e).animationName, getComputedStyle(e).mixBlendMode]") == ["topbar-deep-drift", "normal"]
    inks = belt.evaluate("""e => [...e.querySelectorAll('[style*="color-mix"]')].flatMap(el =>
      [...el.getAttribute('style').matchAll(/var\\(--fx-ink\\) ([\\d.]+)%/g)].map(m => Number(m[1])))""")
    assert inks and max(inks) <= 20, max(inks)


def test_deep_fields_shooting_stars_showers_and_comets_fly_in_front_of_the_sky(page: Any) -> None:
    """David, 10 Nov 2026: now and then a shooting star, a meteor shower or a comet crosses, after the craft lane and
    blended with lighten like the craft, so over a star or a planet the brighter shows and nothing adds up."""
    open_page(page, "/review")
    fx = page.locator("header.topbar > .topbar-deep")
    order = fx.evaluate("e => [...e.children].map(c => c.className)")
    assert order[-2:] == ["topbar-deep-lane", "topbar-deep-events"], order
    probe = fx.evaluate("""e => { const el = document.createElement('div'); el.className = 'topbar-deep-meteor';
      e.querySelector('.topbar-deep-events').appendChild(el); const s = getComputedStyle(el);
      const out = [s.mixBlendMode, s.position]; el.remove(); return out; }""")
    assert probe == ["lighten", "absolute"]


def test_deep_fields_planets_keep_their_sky_and_their_place_across_pages(page: Any) -> None:
    """Moving to another page draws the bar afresh; the planets are the same and carry on from where they were."""
    open_page(page, "/review")
    wait_for_planets(page)
    before = page.evaluate(PLANETS)
    belt_time = "() => document.querySelector('header.topbar .topbar-deep-planets').getAnimations()[0].currentTime"
    then = page.evaluate(belt_time)
    page.locator(".topbar nav a", has_text="Proposals").click()
    page.wait_for_url("**/proposals**")
    page.wait_for_timeout(800)
    wait_for_planets(page)
    assert page.evaluate(PLANETS) == before
    assert page.evaluate(belt_time) >= then + 500


def test_deep_fields_stars_and_craft_never_add_up_behind_a_label(page: Any) -> None:
    """9 Nov 2026: each star layer and each craft paints its own opaque grey and blends with lighten, so where two
    overlap the brighter shows, never the sum, and no pixel behind a label is brighter than the brightest single star."""
    open_page(page, "/review")
    layers = page.evaluate("""() => [...document.querySelectorAll('header.topbar .topbar-deep-stars')].map(e => {
      const s = getComputedStyle(e); return [s.mixBlendMode, s.opacity, s.backgroundColor]; })""")
    assert len(layers) == 3
    for blend, opacity, colour in layers:
        assert blend == "lighten" and opacity == "1", (blend, opacity)
        assert "/" not in colour and "rgba" not in colour, colour   # an opaque grey, not ink at an alpha
    probe = page.evaluate("""() => { const el = document.createElement('div'); el.className = 'topbar-deep-craft';
      document.querySelector('header.topbar .topbar-deep').appendChild(el);
      const blend = getComputedStyle(el).mixBlendMode; el.remove(); return blend; }""")
    assert probe == "lighten"


def test_the_unsure_view_lists_only_calls_held_for_the_team(page: Any) -> None:
    """David, 16 Nov 2026: Unsure holds a call for the team; its card is second on Calls, and the calls it lists have no
    team decision yet, each with someone's amber unsure vote."""
    open_page(page, "/review?view=unsure")
    labels = [t.strip().lower() for t in page.locator(".view-cards .vt-card .vt-card__label").all_inner_texts()]
    assert labels[:3] == ["needs review", "unsure", "top 10"]
    card = page.locator(".view-cards .vt-card[aria-current=page]")
    assert card.locator(".vt-card__label").inner_text().strip().lower() == "unsure"
    rows = page.locator("table.calls-table tbody tr")
    if rows.count() == 0:
        assert "hold it for the team" in page.locator(".empty").inner_text()   # nobody is holding a call
        return
    assert page.locator("table.calls-table tbody .badge", has_text="unsure").count() >= 1
