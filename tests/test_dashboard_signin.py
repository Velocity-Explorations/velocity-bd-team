"""Google sign-in inside the dashboard (U7, phase 11), against the built dashboard with sign-in switched on by made-up
client values: signed-out pages go to /login and come back, the old name cookie counts for nothing, the page says why,
and Sign in with Google sends the person to Google for the company's domain. Google itself is never reached: the
browser's request to it is stopped and read.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. No database is needed: signed out, nothing reads it.
"""
from __future__ import annotations

import os
import re
import secrets
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from tests.test_dashboard_workspace import DASHBOARD, _kill, _wait

pytestmark = pytest.mark.skipif(not os.environ.get("WORKSPACE_TESTS"),
                                reason="set WORKSPACE_TESTS=1 (needs a built dashboard)")

PORT = 8003
WEB = f"http://localhost:{PORT}"


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


def get(path: str, cookie: str = "") -> tuple[int, str]:
    """A request that does not follow redirects: its status and Location (or body for a 200)."""
    opener = urllib.request.build_opener(NoRedirect)
    request = urllib.request.Request(f"{WEB}{path}", headers={"Cookie": cookie} if cookie else {})
    try:
        with opener.open(request, timeout=30) as response:
            return response.status, response.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.headers.get("Location") or ""


@pytest.fixture(scope="module")
def server() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    env = {**os.environ, "AUTH_GOOGLE_ID": "test-client.apps.googleusercontent.com", "AUTH_GOOGLE_SECRET": "not-a-real-secret",
           "AUTH_SECRET": secrets.token_hex(32), "DASHBOARD_USERS": "David Wood <david@velocityexplorations.com>",
           "DATABASE_URL": "postgresql://nobody@127.0.0.1:1/none", "DASHBOARD_IAP_AUDIENCE": "", "DASHBOARD_USER_HEADER": ""}
    process = subprocess.Popen(["node", str(Path("node_modules") / "next" / "dist" / "bin" / "next"), "start", "--port", str(PORT)],
                               cwd=DASHBOARD, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait(lambda: get("/healthz")[0] == 200, "The dashboard with sign-in on port 8003")
        yield
    finally:
        _kill(process)


def test_signed_out_every_page_goes_to_sign_in_and_comes_back(server: None) -> None:
    status, location = get("/proposals/sam-1?step=final")
    assert status in (302, 307)
    parts = urllib.parse.urlsplit(location)
    assert parts.path == "/login" and urllib.parse.parse_qs(parts.query) == {"from": ["/proposals/sam-1?step=final"]}
    assert urllib.parse.urlsplit(get("/")[1]).query == ""   # home needs no from
    # The old name picker's cookie counts for nothing once sign-in is on.
    status, location = get("/review", cookie="bd_viewer=David Wood")
    assert status in (302, 307) and urllib.parse.urlsplit(location).path == "/login"


def test_a_session_that_ended_reads_timed_out(server: None) -> None:
    status, location = get("/calls", cookie="bd_was_signed_in=1")
    assert "reason=timed_out" in location


def test_the_sign_in_page_its_files_and_the_health_check_need_no_session(server: None) -> None:
    status, body = get("/login")
    assert status == 200 and "Sign in with Google" in body
    chunk = re.search(r'/_next/static/[^"]+\.(?:js|css)', body)
    assert chunk and get(chunk.group(0))[0] == 200
    assert get("/velocity-mark-white.png")[0] == 200
    assert get("/healthz")[0] == 200


@pytest.fixture()
def page(server: None) -> Iterator[Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_context(viewport={"width": 1280, "height": 900}).new_page()
        browser.close()


def test_the_sign_in_page_says_why_in_words(page: Any) -> None:
    page.goto(f"{WEB}/login?error=AccessDenied", wait_until="load", timeout=60_000)
    card = page.locator(".login-card")
    assert "That Google account is not on the BD Team list" in card.inner_text()
    assert card.get_by_role("link", name="Reset password").get_attribute("href") == "https://accounts.google.com/signin/recovery"
    assert "need access? ask an admin" in card.inner_text().lower()
    page.goto(f"{WEB}/login?reason=signed_out", wait_until="load", timeout=60_000)
    assert "You are signed out." in page.locator(".login-card").inner_text()


def test_sign_in_with_google_asks_google_for_the_company_account(page: Any) -> None:
    asked: list[str] = []

    def stop(route: Any) -> None:
        asked.append(route.request.url)
        route.abort()

    page.route(re.compile(r"^https://accounts\.google\.com/"), stop)
    page.goto(f"{WEB}/login?from=/proposals", wait_until="load", timeout=60_000)
    page.get_by_role("button", name="Sign in with Google").click()
    page.wait_for_timeout(4000)
    assert asked, "the browser was never sent to Google"
    query = urllib.parse.parse_qs(urllib.parse.urlsplit(asked[0]).query)
    assert query["client_id"] == ["test-client.apps.googleusercontent.com"]
    assert query["hd"] == ["velocityexplorations.com"] and query["prompt"] == ["select_account"]
    assert query["redirect_uri"] == [f"{WEB}/api/auth/callback/google"]
