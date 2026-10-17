"""Form-discovery and OTP-entry logic against local HTML in real headless Chromium.
The HTML mirrors data/recon_login.json: anonymous inputs, only placeholders to go on."""
from __future__ import annotations

from collections.abc import Iterator

import pytest

from portals.shared import browser
from portals.vulcan_sof import auth

LOGIN_HTML = """
<html><body>
<h2>Log in to continue</h2>
<label>Email *</label><input type="text" placeholder="name@agency.mil">
<label>Password *</label><input type="password" placeholder="Enter your password">
<button disabled>Log in</button>
</body></html>
"""

OTP_HTML = """
<html><body>
<h2>Enter the passcode we emailed you</h2>
<input type="text" placeholder="6-digit code">
<button type="submit" disabled>Verify</button>
<script>
  window.submitted = null;
  document.querySelector('button').addEventListener('click', () => {
    window.submitted = document.querySelector('input').value;
  });
</script>
</body></html>
"""


@pytest.fixture(scope="module")
def page() -> Iterator[object]:
    pw, b, ctx, pg = browser.launch()
    try:
        yield pg
    finally:
        browser.close_all(pw, b, ctx, pg)


def test_username_found_by_placeholder_at(page) -> None:
    page.set_content(LOGIN_HTML)
    handle, used = auth.find_username_input(page)
    assert handle is not None
    assert used == "input[placeholder*='@']"
    assert handle.get_attribute("placeholder") == "name@agency.mil"


def test_username_fallback_is_input_before_password(page) -> None:
    page.set_content('<input type="text"><input type="password">')
    handle, used = auth.find_username_input(page)
    assert handle is not None and used == "input-before-password[0]"
    page.set_content('<input type="password">')
    assert auth.find_username_input(page) == (None, "none")


def test_is_logged_in_and_otp_detection(page) -> None:
    page.set_content(LOGIN_HTML)
    assert auth.is_logged_in(page) is False          # about:blank has no 'login', body says 'Log in'
    assert auth.otp_screen_showing(page) is False
    page.set_content(OTP_HTML)
    assert auth.otp_screen_showing(page) is True
    page.set_content("<html><body><h1>Search calls</h1><a href='x?collectionUuid=1'>c</a></body></html>")
    assert auth.is_logged_in(page) is True


def test_submit_otp_types_code_and_force_enables_button(page) -> None:
    page.set_content(OTP_HTML)
    how = auth.submit_otp(page, "482913")
    assert how == "button 'Verify'"
    assert page.evaluate("() => window.submitted") == "482913"
    assert page.evaluate("() => document.querySelector('button').disabled") is False


def test_submit_otp_falls_back_to_enter(page) -> None:
    page.set_content(
        "<input type='tel'><script>window.keys=[];document.querySelector('input')"
        ".addEventListener('keydown', e => window.keys.push(e.key));</script>"
    )
    assert auth.submit_otp(page, "123456") == "Enter key"
    assert page.evaluate("() => window.keys.at(-1)") == "Enter"
    assert page.evaluate("() => document.querySelector('input').value") == "123456"


def test_login_with_bad_page_returns_false_without_raising(page, monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_goto(url: str, **kwargs: object) -> None:
        page.set_content("<html><body>Maintenance. Please sign in later.</body></html>")

    monkeypatch.setattr(page, "goto", fake_goto)
    assert auth.login(page, None, "user@example.invalid", "pw") is False
