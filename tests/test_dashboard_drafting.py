"""Start the draft (P6, P8, Q17, PRO-576): Calls and Proposals carry the dialog, a pursued call's Start
the draft button opens it for that call, `?start=<id>` opens it on arrival, and until the worker has
run it says Drafting is not set up yet with Start held back.

These only read, never write to the ledger: no test presses Start. Name a serving dashboard in
DASHBOARD_TEST_URL; without it they are skipped.
"""
from __future__ import annotations

import os
from datetime import date
from typing import Any
from urllib.parse import quote

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


def first_start_button(page: Any) -> Any | None:
    """The first Start the draft button on To draft, else on All calls' pursued calls; None when neither has one."""
    for path in ("/proposals", "/calls?status=pursue"):
        open_page(page, path)
        button = page.locator("button[data-start-draft]").first
        if button.count():
            return button
    return None


def stand_in_button(page: Any) -> Any:
    """A Start the draft button added to To draft in this browser only, for a ledger with no pursued call.
    The dialog opens from any such button; no test presses Start, so the made-up call is never sent."""
    open_page(page, "/proposals")
    page.evaluate("""() => {
        const b = document.createElement("button");
        b.type = "button";
        b.textContent = "Start the draft";
        Object.assign(b.dataset, { startDraft: "test-only-call", title: "Test only call", portal: "SAM.gov",
                                   due: "2026-11-30", format: "RFI response" });
        document.querySelector("main").append(b);
    }""")
    return page.locator("button[data-start-draft='test-only-call']")


@pytest.mark.parametrize("path, has_dialog", [("/proposals", True), ("/review", True), ("/calls", True), ("/runs", False)])
def test_calls_and_proposals_carry_the_dialog_closed(page: Any, path: str, has_dialog: bool) -> None:
    open_page(page, path)
    dialog = page.locator("dialog#start-draft")
    assert dialog.count() == (1 if has_dialog else 0)
    if has_dialog:
        assert not dialog.evaluate("d => d.open")


def test_start_the_draft_opens_for_its_call_and_cancel_hands_focus_back(page: Any) -> None:
    button = first_start_button(page) or stand_in_button(page)
    call_id = button.get_attribute("data-start-draft")
    title = button.get_attribute("data-title")
    format_ = button.get_attribute("data-format")
    button.click()
    dialog = page.locator("dialog#start-draft")
    dialog.locator("h2", has_text="Start the draft").wait_for(timeout=10_000)
    assert dialog.evaluate("d => d.open")
    assert title in dialog.locator(".lead").inner_text()
    assert dialog.locator("select[name=format]").input_value() == format_
    assert dialog.locator("input[name=approval_mode][value=every_step]").is_checked()
    assert dialog.locator("input[name=call_id]").input_value() == call_id
    assert f"Submissions/{date.today().isoformat()}_" in dialog.locator(".draft-folder").inner_text()
    start = dialog.get_by_role("button", name="Start the draft")
    if "Drafting is not set up yet." in dialog.inner_text():
        assert start.is_disabled()   # P8: nothing to spend on until the worker has run
    dialog.get_by_role("button", name="Cancel").click()
    page.wait_for_timeout(200)
    assert not dialog.evaluate("d => d.open")
    assert page.evaluate("() => document.activeElement?.dataset?.startDraft ?? null") == call_id


def test_the_start_address_opens_the_dialog_on_arrival(page: Any) -> None:
    button = first_start_button(page)
    if button is None:
        pytest.skip("no pursued call is waiting for a draft")
    call_id = button.get_attribute("data-start-draft")
    path = "/proposals" if page.url.rstrip("/").endswith("/proposals") else "/calls?status=pursue"
    sep = "&" if "?" in path else "?"
    open_page(page, f"{path}{sep}start={quote(call_id)}")
    dialog = page.locator("dialog#start-draft")
    dialog.locator("input[name=call_id]").wait_for(state="attached", timeout=10_000)
    assert dialog.evaluate("d => d.open")
    assert dialog.locator("input[name=call_id]").input_value() == call_id
    assert "start=" not in dialog.locator("input[name=return_to]").input_value()
