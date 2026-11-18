"""Deciding a call from the Decide menu (Task 1 of the 9 Nov call, 18 Nov 2026), in a browser against a throwaway Postgres,
never the live ledger.

Pursue saves on the first click from Home's Top 10 and from Calls. While it saves, the button says Saving and the menu
cannot be chosen again; then the page comes back to the row, whose Decide cell says Saved (or why nothing was saved) beside
the person's own vote. A second Pursue from a page that had not reloaded is already saved, never refused, and writes no
second vote. A call someone else changed since the page showed it is refused at the row. Another person still sees the
call waiting for their decision.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine container
(Docker) and the built dashboard on port 8006 against it, and remove both at the end.
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
DB_PORT, WEB_PORT = 54333, 8006
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones"

HOME = "decide-home"          # in the Monday brief's Top 10, undecided
LOW = "decide-low"            # oldest, so it sits at the foot of All calls
TWICE = "decide-twice"        # chosen from two tabs that both showed it undecided
MOVED = "decide-moved"        # Shaun decides it after David's page showed it undecided
QUEUED = "decide-queued"      # decided from Needs review, which it then leaves
FILLERS = 30


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


def _db_ready() -> bool:
    return _sql("SELECT 1") == [(1,)]


def _web_ready() -> bool:
    with urllib.request.urlopen(f"{WEB}/healthz", timeout=3) as response:
        return response.status == 200


def _kill(process: subprocess.Popen[bytes]) -> None:
    if sys.platform == "win32":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=60)
    else:
        process.terminate()
    process.wait(timeout=30)


def _call(call_id: str, title: str, seen: str) -> None:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": title, "type": "Sources Sought", "department": "DEPT OF THE ARMY",
                    "due_date": "2027-01-15", "url": f"https://example.invalid/{call_id}",
                    "description": "Seeded for the Decide menu tests."}, run_id)
    _sql("UPDATE calls SET filter_result = 'kept', ai_verdict = 'yes', ai_reasoning = 'Seeded.', first_seen_at = %s WHERE id = %s",
         (seen, call_id))


def seed() -> None:
    _call(LOW, "Decide low call", "2026-11-01T00:00:00Z")
    _call(HOME, "Decide home call", "2026-11-02T00:00:00Z")
    _call(TWICE, "Decide twice call", "2026-11-03T00:00:00Z")
    _call(MOVED, "Decide moved call", "2026-11-04T00:00:00Z")
    _call(QUEUED, "Decide queued call", "2026-11-05T00:00:00Z")
    for n in range(FILLERS):   # newer, so All calls (newest first) puts them above the calls under test
        _call(f"decide-filler-{n:02d}", f"Decide filler {n:02d}", f"2026-11-10T00:{n:02d}:00Z")
    lq.save_brief("2026-11-16", None, {"top": [{"id": HOME, "title": "Decide home call", "portal": "SAM.gov"}], "watch": [],
                                       "ranked_by": "seeded"}, "tests")


@pytest.fixture(scope="module")
def site() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-decide-test-{os.getpid()}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{DB_PORT}:5432",
                    "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:17-alpine"], check=True, capture_output=True, timeout=180)
    try:
        _wait(_db_ready, "The throwaway Postgres")
        migrate.apply(DB_URL)
        with ledger():
            seed()
        # Sign-in off whatever dashboard/.env.local holds: these tests choose who is signed in with the picker.
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
def browser(site: None) -> Iterator[Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def new_page(browser: Any) -> Any:
    return browser.new_context(viewport={"width": 1440, "height": 900}).new_page()


def log_in(page: Any, name: str) -> None:
    page.goto(f"{WEB}/calls", wait_until="load", timeout=120_000)
    menu = page.locator(".topbar details.account")
    menu.locator("summary").click()
    menu.locator("form.choose-viewer button[name=viewer]", has_text=name).click()
    page.wait_for_timeout(1500)


def row_on(page: Any, path: str, call_id: str) -> Any:
    page.goto(f"{WEB}{path}", wait_until="load", timeout=120_000)
    page.wait_for_timeout(1500)   # the Decide menu's client parts hydrate
    row = page.locator(f"tr[data-call-id='{call_id}']")
    row.scroll_into_view_if_needed()
    return row


def choose(row: Any, status: str) -> None:
    row.locator("details.decide-menu > summary").click()
    row.locator(f".decide-menu button[name=status][value={status}]").click()


def came_back(page: Any) -> None:
    page.wait_for_url(re.compile(r"[?&](notice|error)="), timeout=30_000)
    page.wait_for_timeout(800)   # the scroll to the row follows the new page


def in_view(row: Any) -> bool:
    return bool(row.evaluate("el => { const r = el.getBoundingClientRect(); return r.top >= 0 && r.bottom <= window.innerHeight; }"))


def votes_of(call_id: str) -> list[tuple[str, str]]:
    return [(r[0], r[1]) for r in _sql("SELECT decided_by, status FROM decisions WHERE call_id = %s ORDER BY id", (call_id,))]


def decision_of(call_id: str) -> tuple[str | None, str | None]:
    (row,) = _sql("SELECT human_status, human_by FROM calls WHERE id = %s", (call_id,))
    return row[0], row[1]


def test_pursue_on_all_calls_says_saving_then_comes_back_to_the_row_saved(browser: Any) -> None:
    page = new_page(browser)
    log_in(page, "David Wood")
    row = row_on(page, "/calls", LOW)
    held: list[Any] = []

    def hold(route: Any) -> None:
        if route.request.method == "POST" and "next-action" in route.request.headers:
            held.append(route)
        else:
            route.continue_()

    page.route(re.compile(".*"), hold)
    choose(row, "pursue")
    from playwright.sync_api import expect

    summary = row.locator("details.decide-menu > summary")
    expect(summary).to_contain_text("Saving", timeout=5_000)
    expect(row.locator(".decide-menu button[name=status][value=dismissed]")).to_be_disabled()
    assert len(held) == 1
    held[0].continue_()
    page.unroute(re.compile(".*"))
    came_back(page)

    row = page.locator(f"tr[data-call-id='{LOW}']")
    assert in_view(row), "the page did not come back to the row the decision was made on"
    cell = row.locator("td.decide")
    expect(cell.locator(".decide-outcome")).to_have_text("Saved")
    expect(cell).to_contain_text("You: Pursue")
    assert decision_of(LOW) == ("pursue", "David Wood")
    assert votes_of(LOW) == [("David Wood", "pursue")]

    page.reload(wait_until="load")   # it survives a refresh
    expect(page.locator(f"tr[data-call-id='{LOW}'] td.decide")).to_contain_text("You: Pursue")

    other = new_page(browser)   # Shaun still has it to decide
    log_in(other, "Shaun Jones")
    shaun = row_on(other, "/calls", LOW)
    expect(shaun.locator("td.decide")).to_contain_text("needs your decision")
    expect(shaun.locator("td.decide")).not_to_contain_text("You:")


def test_pursue_on_homes_top_10_saves_on_the_first_click_and_stays_on_the_row(browser: Any) -> None:
    from playwright.sync_api import expect

    page = new_page(browser)
    log_in(page, "David Wood")
    page.goto(f"{WEB}/", wait_until="load", timeout=120_000)
    page.wait_for_timeout(1500)
    row = page.locator(f"tr[data-call-id='{HOME}']")
    choose(row, "pursue")
    came_back(page)
    assert re.search(r"^/(\?|$)", page.url.removeprefix(WEB)), page.url   # still Home
    row = page.locator(f"tr[data-call-id='{HOME}']")
    expect(row.locator(".decide-outcome")).to_have_text("Saved")
    expect(row.locator("td.decide")).to_contain_text("You: Pursue")
    assert decision_of(HOME) == ("pursue", "David Wood")
    assert votes_of(HOME) == [("David Wood", "pursue")]


def test_a_second_pursue_from_a_page_that_had_not_reloaded_is_already_saved(browser: Any) -> None:
    from playwright.sync_api import expect

    first = new_page(browser)
    log_in(first, "David Wood")
    second = first.context.new_page()   # the same person, a second tab showing the call undecided
    row_a = row_on(first, "/calls", TWICE)
    row_b = row_on(second, "/calls", TWICE)
    choose(row_a, "pursue")
    came_back(first)
    choose(row_b, "pursue")
    came_back(second)
    row_b = second.locator(f"tr[data-call-id='{TWICE}']")
    expect(row_b.locator(".decide-outcome")).to_have_text("Already saved")
    assert "error=" not in second.url
    assert votes_of(TWICE) == [("David Wood", "pursue")]   # one vote, not two
    assert decision_of(TWICE) == ("pursue", "David Wood")


def test_a_call_changed_since_the_page_showed_it_is_refused_at_the_row(browser: Any) -> None:
    from playwright.sync_api import expect

    page = new_page(browser)
    log_in(page, "David Wood")
    row = row_on(page, "/calls", MOVED)
    with ledger():
        lq.set_human(MOVED, "not_relevant", "Shaun Jones")
    choose(row, "pursue")
    came_back(page)
    row = page.locator(f"tr[data-call-id='{MOVED}']")
    assert in_view(row)
    outcome = row.locator(".decide-outcome")
    expect(outcome).to_contain_text("changed meanwhile")
    assert "tone-conflict" in (outcome.get_attribute("class") or "")
    assert decision_of(MOVED) == ("not_relevant", "Shaun Jones")
    assert votes_of(MOVED) == [("Shaun Jones", "not_relevant")]


def test_a_decision_from_needs_review_says_so_at_the_top_when_the_call_leaves_the_queue(browser: Any) -> None:
    from playwright.sync_api import expect

    page = new_page(browser)
    log_in(page, "David Wood")
    row = row_on(page, "/review", QUEUED)
    choose(row, "pursue")
    came_back(page)
    expect(page.locator(f"tr[data-call-id='{QUEUED}']")).to_have_count(0)   # it left David's queue
    notice = page.locator(".notice.tone-good")
    expect(notice).to_contain_text("Decide queued call")
    assert in_view(notice)
    assert votes_of(QUEUED) == [("David Wood", "pursue")]
