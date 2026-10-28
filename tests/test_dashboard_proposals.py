"""The Proposals section's five views (PRO-575): five cards in order, To draft first in the accent,
each address pressing its own card, and the filter bar without Table settings.

These only read, never write to the ledger. Name a serving dashboard in DASHBOARD_TEST_URL; without it
they are skipped.
"""
from __future__ import annotations

import os
from typing import Any

import pytest

URL = os.environ.get("DASHBOARD_TEST_URL", "").rstrip("/")
pytestmark = pytest.mark.skipif(not URL, reason="set DASHBOARD_TEST_URL to a running dashboard")

PRESSED = {
    "/proposals": "to draft",
    "/proposals?view=closing": "closing in 14 days",
    "/proposals?view=drafting": "drafting",
    "/proposals/submitted": "submitted and waiting",
    "/proposals/results": "results",
}


@pytest.fixture(scope="module")
def page() -> Any:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_page(viewport={"width": 1440, "height": 900})
        browser.close()


def open_page(page: Any, path: str) -> None:
    page.goto(URL + path, wait_until="load", timeout=120_000)
    page.wait_for_timeout(300)


def test_proposals_has_five_cards_in_order(page: Any) -> None:
    open_page(page, "/proposals")
    labels = [t.strip().lower() for t in page.locator(".view-cards .vt-card__label").all_inner_texts()]
    assert labels == ["closing in 14 days", "to draft", "drafting", "submitted and waiting", "results"]


@pytest.mark.parametrize("path", list(PRESSED))
def test_each_address_presses_its_card_and_keeps_the_bar(page: Any, path: str) -> None:
    open_page(page, path)
    pressed = [t.strip().lower() for t in page.locator(".view-cards .vt-card[aria-current=page] .vt-card__label").all_inner_texts()]
    assert pressed == [PRESSED[path]]
    bar = page.locator(".filter-bar")
    assert "Portals" in bar.inner_text()
    assert bar.get_by_role("button", name="Table settings").count() == 0
    assert page.locator("table.proposals-table").count() + page.locator(".empty").count() >= 1
