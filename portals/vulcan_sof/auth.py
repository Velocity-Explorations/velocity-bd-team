"""Log in to Vulcan SOF: username and password, then the emailed one-time code.

    ok = login(page, context, username, password)

Everything here follows the reference adapter's hard-won rules (reference/yukon/vulcan_sof.py):
anchor on the password field, cascade selectors for the username, type the OTP character
by character so Angular's validators fire, force-enable the verify button, and never wait
for networkidle. The password is never logged. The six-digit code may be.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from playwright.sync_api import BrowserContext, ElementHandle, Page

from portals.vulcan_sof.otp import get_otp
from portals.vulcan_sof.session import load_cookies, save_cookies

log = logging.getLogger("vulcan_sof.auth")

APP_PREFIX = "/login/ng2/"
LOGIN_URL = "https://vulcan-sof.com/login/ng2/auth/login"
CALLS_URL = "https://vulcan-sof.com/login/ng2/search/calls"

PASSWORD_SELECTOR = "input[type='password']"
USERNAME_SELECTORS = [
    "input[type='email']",
    "input[name*='email']",
    "input[name*='user']",
    "input[placeholder*='email' i]",
    "input[placeholder*='user' i]",
    "input[placeholder*='@']",
    "input[autocomplete='username']",
    "input[autocomplete='email']",
]
OTP_INPUT_SELECTORS = [
    "input[name*='otp']",
    "input[name*='code']",
    "input[name*='passcode']",
    "input[type='tel']",
    "input[type='number']",
    "input[type='text']",
    "input",
]
OTP_MARKERS = ("passcode", "one-time", "verification")
OTP_TYPE_DELAY_MS = 80

CLICK_SUBMIT_JS = """
() => {
  const words = ['verify', 'verify code', 'submit', 'confirm', 'continue'];
  const buttons = Array.from(document.querySelectorAll('button'));
  let target = buttons.find(b => words.includes((b.innerText || b.textContent || '').trim().toLowerCase()));
  if (!target) target = buttons.find(b => (b.getAttribute('type') || '').toLowerCase() === 'submit');
  if (!target) return null;
  target.disabled = false;
  target.removeAttribute('disabled');
  target.click();
  return (target.innerText || target.textContent || '').trim();
}
"""

INPUT_BEFORE_PASSWORD_JS = """
() => {
  const inputs = Array.from(document.querySelectorAll('input'));
  const idx = inputs.findIndex(el => el.type === 'password');
  return idx > 0 ? idx - 1 : -1;
}
"""


def body_text(page: Page, limit: int) -> str:
    try:
        text = page.evaluate("() => document.body ? document.body.innerText : ''")
    except Exception:
        return ""
    return " ".join(text.split())[:limit]


def is_logged_in(page: Page) -> bool:
    """True unless the URL or the top of the page says we are on the sign-in flow.

    The whole Angular app is served under /login/ng2/, so that prefix is dropped before
    the word "login" is tested; otherwise the calls listing itself would count as logged out.
    """
    url = page.url.lower().replace(APP_PREFIX, "/")
    if "login" in url and "home" not in url:
        return False
    head = body_text(page, 200).lower()
    if "sign in" in head or "log in" in head:
        return False
    return True


def otp_screen_showing(page: Page) -> bool:
    text = body_text(page, 5000).lower()
    return any(marker in text for marker in OTP_MARKERS)


def find_username_input(page: Page) -> tuple[ElementHandle | None, str]:
    """First matching cascade selector, else the input just before the password field."""
    for selector in USERNAME_SELECTORS:
        handle = page.query_selector(selector)
        if handle is not None:
            return handle, selector
    idx = page.evaluate(INPUT_BEFORE_PASSWORD_JS)
    if idx is not None and idx >= 0:
        handles = page.query_selector_all("input")
        if idx < len(handles):
            return handles[idx], f"input-before-password[{idx}]"
    return None, "none"


def find_otp_input(page: Page) -> tuple[ElementHandle | None, str]:
    for selector in OTP_INPUT_SELECTORS:
        handle = page.query_selector(selector)
        if handle is not None:
            return handle, selector
    return None, "none"


def submit_otp(page: Page, code: str) -> str:
    """Type the code and submit. Returns how it was submitted, for the log."""
    field, selector = find_otp_input(page)
    if field is None:
        raise RuntimeError("no input on the OTP screen")
    log.info("OTP input selector: %s", selector)
    field.click(timeout=5_000)
    field.click(click_count=3, timeout=5_000)
    field.type(code, delay=OTP_TYPE_DELAY_MS, timeout=15_000)
    page.wait_for_timeout(800)
    clicked = page.evaluate(CLICK_SUBMIT_JS)
    if clicked is not None:
        return f"button '{clicked}'"
    field.press("Enter", timeout=5_000)
    return "Enter key"


def _settle(page: Page, after_ms: int) -> None:
    try:
        page.wait_for_load_state("domcontentloaded", timeout=15_000)
    except Exception:
        pass
    page.wait_for_timeout(after_ms)


def login(page: Page, context: BrowserContext | None, username: str, password: str) -> bool:
    """Cookie-first login. Returns True when the calls listing is reachable. Never raises."""
    try:
        if context is not None and _restore_session(page, context):
            return True
        ok = _login(page, username, password)
        if ok and context is not None:
            save_cookies(context)
        return ok
    except Exception as exc:
        log.error("Login failed with %s: %s", type(exc).__name__, str(exc)[:200])
        _log_failure_context(page)
        return False


def _restore_session(page: Page, context: BrowserContext) -> bool:
    """Load saved cookies and see whether the calls listing opens without signing in."""
    if not load_cookies(context):
        return False
    try:
        page.goto(CALLS_URL, timeout=20_000, wait_until="domcontentloaded")
        page.wait_for_timeout(3_000)
        if is_logged_in(page):
            log.info("Session restored from cookies, no OTP needed")
            return True
        log.info("Saved cookies expired (landed on %s); logging in with password", page.url)
    except Exception as exc:
        log.info("Saved cookies unusable (%s: %s); logging in with password", type(exc).__name__, str(exc)[:120])
    return False


def _login(page: Page, username: str, password: str) -> bool:
    page.goto(LOGIN_URL, timeout=30_000, wait_until="domcontentloaded")
    _settle(page, 2_000)
    log.info("Login page loaded: %s", page.url)

    password_field = page.query_selector(PASSWORD_SELECTOR)
    if password_field is None:
        try:
            page.wait_for_selector(PASSWORD_SELECTOR, timeout=10_000)
        except Exception:
            pass
        password_field = page.query_selector(PASSWORD_SELECTOR)
    if password_field is None:
        log.error("No password field on the login page")
        _log_failure_context(page)
        return False

    username_field, used = find_username_input(page)
    if username_field is None:
        log.error("No username field found")
        _log_failure_context(page)
        return False
    log.info("Username selector used: %s", used)

    login_triggered_at = time.time()
    username_field.click(timeout=5_000)
    username_field.fill(username, timeout=5_000)
    if not password_field.is_visible():
        log.info("Password field hidden after username; waiting for it")
        page.wait_for_selector(f"{PASSWORD_SELECTOR}:visible", timeout=10_000)
        password_field = page.query_selector(PASSWORD_SELECTOR) or password_field
    password_field.click(timeout=5_000)
    password_field.fill(password, timeout=5_000)
    password_field.press("Enter", timeout=5_000)
    page.wait_for_timeout(3_000)
    log.info("Submitted credentials; now at %s", page.url)

    if otp_screen_showing(page):
        log.info("OTP required: yes")
        started = time.time()
        code = get_otp(sent_after=login_triggered_at)
        if code is None:
            log.error("OTP not received; aborting login")
            _log_failure_context(page)
            return False
        log.info("OTP retrieved in %.0f s", time.time() - started)
        how = submit_otp(page, code)
        log.info("OTP submitted via %s", how)
        _settle(page, 3_000)
        log.info("Post-OTP URL: %s", page.url)
    else:
        log.info("OTP required: no")

    if is_logged_in(page):
        log.info("Logged in: %s", page.url)
        return True
    log.error("Not logged in after submit")
    _log_failure_context(page)
    return False


def _log_failure_context(page: Page) -> None:
    log.error("URL: %s | body: %s", page.url, body_text(page, 150))


def open_calls(page: Page) -> Any:
    """Navigate to the calls listing with the standard waits."""
    page.goto(CALLS_URL, timeout=30_000, wait_until="domcontentloaded")
    _settle(page, 3_000)
    return page.url
