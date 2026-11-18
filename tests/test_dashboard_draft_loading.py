"""Start the draft while it waits on the server (Task 2 of the 9 Nov call, 18 Nov 2026), in a browser against a throwaway
Postgres, never the live ledger.

Suggest says Asking Claude... with a turning ring from the click, then what Claude is doing, and Start waits until the
suggestion lands, unless the assistant is offline, when the request is parked and Start stays open. A request that does
not go through, or a suggestion that fails, says so with Retry. Start says Starting... while it posts, and the notice
after it says where the draft shows up.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine container
(Docker) and the built dashboard on port 8007 against it, and remove both at the end.
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

from ledger import migrate
from ledger import queries as lq

pytestmark = pytest.mark.skipif(not os.environ.get("WORKSPACE_TESTS"),
                                reason="set WORKSPACE_TESTS=1 (needs Docker and a built dashboard)")

REPO = Path(__file__).resolve().parent.parent
DASHBOARD = REPO / "dashboard"
DB_PORT, WEB_PORT = 54334, 8007
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones"

SLOW = "draft-slow"          # Suggest held on its way, then queued, then failed by the assistant, then asked again
BROKEN = "draft-broken"      # the Suggest request does not go through, then Retry
PARKED = "draft-parked"      # Suggest while the assistant is offline
STARTED = "draft-started"    # Start held while it posts, then the notice on Drafting


@contextmanager
def ledger() -> Iterator[None]:
    """The ledger helpers pointed at the throwaway database for a moment."""
    before = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = DB_URL
    try:
        yield
    finally:
        if before is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = before


def _wait(check: Any, what: str, seconds: int = 90) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            if check():
                return
        except Exception:   # noqa: BLE001 (not up yet)
            pass
        time.sleep(1)
    raise RuntimeError(f"{what} did not come up within {seconds} seconds")


def _sql(statement: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    import psycopg

    with psycopg.connect(DB_URL) as conn:
        cur = conn.execute(statement, params)
        return cur.fetchall() if cur.description else []


def _web_ready() -> bool:
    with urllib.request.urlopen(f"{WEB}/healthz", timeout=3) as response:
        return response.status == 200


def _kill(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=60)
    else:
        process.terminate()
    process.wait(timeout=30)


def _pursued(call_id: str, title: str) -> None:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": title, "type": "Sources Sought", "department": "DEPT OF THE ARMY",
                    "due_date": "2027-01-15", "url": f"https://example.invalid/{call_id}",
                    "description": "Seeded for the Start the draft tests."}, run_id)
    _sql("UPDATE calls SET filter_result = 'kept', ai_verdict = 'yes', ai_reasoning = 'Seeded.' WHERE id = %s", (call_id,))
    lq.set_human(call_id, "pursue", "David Wood")


def seed() -> None:
    lq.worker_started(lq.WORKER)      # drafting is set up
    lq.worker_started("assistant")    # and the assistant that answers Suggest is running
    _pursued(SLOW, "Draft slow call")
    _pursued(BROKEN, "Draft broken call")
    _pursued(PARKED, "Draft parked call")
    _pursued(STARTED, "Draft started call")


@pytest.fixture(scope="module")
def site() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-draft-loading-test-{os.getpid()}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{DB_PORT}:5432",
                    "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:17-alpine"], check=True, capture_output=True, timeout=180)
    try:
        _wait(lambda: _sql("SELECT 1") == [(1,)], "The throwaway Postgres")
        migrate.apply(DB_URL)
        with ledger():
            seed()
        env = {**os.environ, "DATABASE_URL": DB_URL, "DASHBOARD_USERS": PEOPLE, "DASHBOARD_IAP_AUDIENCE": "",
               "DASHBOARD_USER_HEADER": "", "DASHBOARD_QUEUE": "", "AUTH_GOOGLE_ID": "", "AUTH_GOOGLE_SECRET": "", "AUTH_SECRET": "",
               "DASHBOARD_CACHE_SECONDS": "0", "DASHBOARD_DB_MAX": "3"}
        server = subprocess.Popen(["node", str(Path("node_modules") / "next" / "dist" / "bin" / "next"), "start", "--port", str(WEB_PORT)],
                                  cwd=DASHBOARD, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            _wait(_web_ready, f"The dashboard on port {WEB_PORT}")
            yield
        finally:
            _kill(server)
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True, timeout=120)


@pytest.fixture()
def page(site: None) -> Iterator[Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        browser.close()


def log_in(page: Any, name: str) -> None:
    page.goto(f"{WEB}/proposals", wait_until="load", timeout=120_000)
    menu = page.locator(".topbar details.account")
    menu.locator("summary").click()
    menu.locator("form.choose-viewer button[name=viewer]", has_text=name).click()
    page.wait_for_timeout(1500)


def open_dialog(page: Any, call_id: str) -> Any:
    page.goto(f"{WEB}/proposals", wait_until="load", timeout=120_000)
    page.wait_for_timeout(1500)   # the dialog's script hydrates
    page.locator(f"[data-start-draft='{call_id}']").first.click()
    dialog = page.locator("dialog#start-draft")
    dialog.wait_for(state="visible", timeout=5_000)
    page.wait_for_timeout(800)    # it reads the call's newest suggestion on opening
    return dialog


class Held:
    """Holds the page's server action requests until released, so what shows while they are on their way can be seen."""

    def __init__(self, page: Any, abort: bool = False) -> None:
        self.page, self.abort, self.routes = page, abort, []

    def __enter__(self) -> "Held":
        self.page.route(re.compile(".*"), self._route)
        return self

    def _route(self, route: Any) -> None:
        if route.request.method == "POST" and "next-action" in route.request.headers:
            if self.abort:
                route.abort()
            else:
                self.routes.append(route)
        else:
            route.continue_()

    def release(self) -> None:
        for route in self.routes:
            route.continue_()
        self.routes = []

    def __exit__(self, *exc: object) -> None:
        self.release()
        self.page.unroute(re.compile(".*"))


def suggest_button(dialog: Any) -> Any:
    return dialog.locator(".suggest-bar button.suggest-ask")


def start_button(dialog: Any) -> Any:
    return dialog.locator(".settings-actions button[type=submit]")


def asked(call_id: str) -> list[tuple[str, str | None]]:
    return [(r[0], r[1]) for r in _sql("SELECT state, note FROM draft_suggestions WHERE call_id = %s ORDER BY id", (call_id,))]


def test_suggest_says_asking_at_once_and_start_waits_until_the_suggestion_lands(page: Any) -> None:
    from playwright.sync_api import expect

    log_in(page, "David Wood")
    dialog = open_dialog(page, SLOW)
    status = dialog.locator(".suggest-bar .hint")
    with Held(page) as held:
        suggest_button(dialog).click()
        expect(status).to_have_text("Asking Claude...", timeout=5_000)
        expect(dialog.locator(".suggest-bar .spin")).to_be_visible()
        expect(suggest_button(dialog)).to_be_disabled()
        expect(start_button(dialog)).to_be_disabled()
        assert len(held.routes) == 1
        held.release()
    expect(status).to_contain_text("Claude is reading the call", timeout=10_000)
    expect(dialog.locator(".suggest-bar .spin")).to_be_visible()
    expect(start_button(dialog)).to_be_disabled()   # it waits for the suggestion
    expect(dialog.locator(".settings-actions")).to_contain_text("Start waits for Claude's suggestion")
    assert asked(SLOW) == [("queued", None)]

    _sql("UPDATE draft_suggestions SET state = 'failed', note = 'Claude could not read the call.' WHERE call_id = %s", (SLOW,))
    error = dialog.locator(".suggest-bar .error-text")
    expect(error).to_contain_text("Claude could not read the call.", timeout=10_000)
    expect(start_button(dialog)).to_be_enabled()   # a failed suggestion holds nothing back
    retry = dialog.locator(".suggest-bar button.suggest-retry")
    expect(retry).to_be_visible()
    retry.click()
    expect(status).to_contain_text("Claude is reading the call", timeout=10_000)
    assert asked(SLOW) == [("failed", "Claude could not read the call."), ("queued", None)]


def test_a_suggest_request_that_does_not_go_through_says_so_with_retry(page: Any) -> None:
    from playwright.sync_api import expect

    log_in(page, "David Wood")
    dialog = open_dialog(page, BROKEN)
    with Held(page, abort=True):
        suggest_button(dialog).click()
        expect(dialog.locator(".suggest-bar .error-text")).to_contain_text("did not go through", timeout=10_000)
    expect(start_button(dialog)).to_be_enabled()
    expect(suggest_button(dialog)).to_be_enabled()
    assert asked(BROKEN) == []
    dialog.locator(".suggest-bar button.suggest-retry").click()
    expect(dialog.locator(".suggest-bar .hint")).to_contain_text("Claude is reading the call", timeout=10_000)
    expect(dialog.locator(".suggest-bar .error-text")).to_have_count(0)
    assert asked(BROKEN) == [("queued", None)]


def test_a_suggestion_parked_while_the_assistant_is_offline_does_not_hold_start(page: Any) -> None:
    from playwright.sync_api import expect

    _sql("UPDATE workers SET seen_at = '2026-11-01T00:00:00Z' WHERE name = 'assistant'")
    try:
        log_in(page, "David Wood")
        dialog = open_dialog(page, PARKED)
        suggest_button(dialog).click()
        expect(dialog.locator(".suggest-bar .hint")).to_contain_text("The assistant is offline", timeout=10_000)
        expect(start_button(dialog)).to_be_enabled()
        expect(dialog.locator(".suggest-bar .spin")).to_have_count(0)
    finally:
        with ledger():
            lq.worker_started("assistant")


def test_start_says_starting_while_it_posts_and_the_notice_says_where_to_look(page: Any) -> None:
    from playwright.sync_api import expect

    log_in(page, "David Wood")
    dialog = open_dialog(page, STARTED)
    with Held(page) as held:
        start_button(dialog).click()
        expect(start_button(dialog)).to_have_text("Starting...", timeout=5_000)
        expect(start_button(dialog)).to_be_disabled()
        expect(suggest_button(dialog)).to_be_disabled()
        assert len(held.routes) == 1
        held.release()
    page.wait_for_url(re.compile(r"/proposals\?view=drafting"), timeout=30_000)
    notice = page.locator(".notice.tone-good")
    expect(notice).to_contain_text("Started the draft for Draft started call")
    expect(notice).to_contain_text("Follow it here under Drafting")
    expect(notice).to_contain_text("02 Submissions")
    assert _sql("SELECT owner FROM pursuits WHERE call_id = %s", (STARTED,)) == [("David Wood",)]
