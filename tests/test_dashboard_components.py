"""The app components behave as the handoff's guides say (PRO-569): menus take focus, move with the
arrow keys and hand focus back; the settings dialog returns focus to its button; hover-only text shows
on keyboard focus; and the page stays dark when the system asks for light.

These only read, never write to the ledger. Name a serving dashboard in DASHBOARD_TEST_URL; without it
they are skipped.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

URL = os.environ.get("DASHBOARD_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_TEST_URL to a running dashboard")

FOCUSED = "() => { const el = document.activeElement; return el ? el.outerHTML.slice(0, 160) : ''; }"


@pytest.fixture()
def page() -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page(viewport={"width": 1440, "height": 900}, color_scheme="light")
        browser.close()


def open_calls(page: Any) -> None:
    page.goto(URL + "/calls", wait_until="load", timeout=120_000)
    page.wait_for_timeout(500)


def test_a_menu_takes_focus_moves_with_arrows_and_hands_focus_back(page: Any) -> None:
    open_calls(page)
    menu = page.locator(".filter-bar details.menu", has_text="Portals")
    summary = menu.locator("summary")
    summary.focus()
    page.keyboard.press("Enter")
    page.wait_for_timeout(200)
    assert menu.evaluate("m => m.open")
    first = page.evaluate(FOCUSED)
    assert menu.evaluate("m => m.querySelector('.menu-body').contains(document.activeElement)"), first
    page.keyboard.press("ArrowDown")
    assert page.evaluate(FOCUSED) != first
    assert menu.evaluate("m => m.querySelector('.menu-body').contains(document.activeElement)")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    assert not menu.evaluate("m => m.open")
    assert summary.evaluate("s => s === document.activeElement")


def test_the_settings_dialog_returns_focus_to_its_button(page: Any) -> None:
    open_calls(page)
    button = page.locator(".filter-bar").get_by_role("button", name="Table settings")
    button.click()
    dialog = page.locator("dialog#table-settings")
    assert dialog.evaluate("d => d.open")
    assert dialog.evaluate("d => d.contains(document.activeElement)")
    page.keyboard.press("Escape")
    page.wait_for_timeout(200)
    assert not dialog.evaluate("d => d.open")
    assert button.evaluate("b => b === document.activeElement")


def test_hover_only_text_shows_on_keyboard_focus(page: Any) -> None:
    open_calls(page)
    tipped = page.locator(".meta [title][tabindex='0']").first
    if tipped.count() == 0:
        pytest.skip("no call on this ledger shows a detail with hover text")
    text = tipped.get_attribute("title")
    tipped.focus()
    tip = page.locator("[role=tooltip]")
    tip.wait_for(state="visible", timeout=2000)
    assert tip.inner_text().strip() == text.strip()
    page.keyboard.press("Escape")
    tip.wait_for(state="hidden", timeout=2000)


def test_the_page_stays_dark_when_the_system_asks_for_light(page: Any) -> None:
    open_calls(page)
    assert page.evaluate("() => getComputedStyle(document.body).backgroundColor") == "rgb(30, 30, 30)"
    assert page.evaluate("() => getComputedStyle(document.body).fontFamily").startswith('"Inter Tight"')
