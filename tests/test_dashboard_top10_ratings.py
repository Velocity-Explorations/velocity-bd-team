"""Rating the Top 10's picks (Task 5 of the 9 Nov call, 18 Nov 2026), in a browser against a throwaway Postgres, never the
live ledger.

On Home each pick in this week's Top 10 takes Good pick, Not a fit or Unsure, with a reason if wanted, from the person
signed in, apart from their decision on the call. Rating again replaces their rating. Everyone else's shows beside it.
Automation's Top 10 reviews lists each week's Top 10 with every reviewer's rating and comment, and whether they agree;
each week keeps its own.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine container
(Docker) and the built dashboard on port 8012 against it, and remove both at the end.
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
DB_PORT, WEB_PORT = 54337, 8012
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones"
WEEK, LAST_WEEK = "2026-11-16", "2026-11-09"

FIRST = "pick-first"     # this week's #1
SECOND = "pick-second"   # this week's #2, and last week's #1


@contextmanager
def ledger() -> Iterator[None]:
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


def _call(call_id: str, title: str) -> None:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": title, "type": "Sources Sought", "department": "DEPT OF THE ARMY",
                    "due_date": "2027-01-15", "url": f"https://example.invalid/{call_id}",
                    "description": "Seeded for the Top 10 rating tests."}, run_id)
    _sql("UPDATE calls SET filter_result = 'kept', ai_verdict = 'yes', ai_reasoning = 'Seeded.' WHERE id = %s", (call_id,))


def seed() -> None:
    _call(FIRST, "First pick call")
    _call(SECOND, "Second pick call")
    lq.save_brief(LAST_WEEK, None, {"top": [{"id": SECOND, "title": "Second pick call", "portal": "SAM.gov"}], "watch": [],
                                    "ranked_by": "seeded"}, "tests")
    lq.save_brief(WEEK, None, {"top": [{"id": FIRST, "title": "First pick call", "portal": "SAM.gov"},
                                       {"id": SECOND, "title": "Second pick call", "portal": "SAM.gov"}], "watch": [],
                               "ranked_by": "seeded"}, "tests")
    _sql("INSERT INTO top10_ratings (week_of, call_id, rated_by, rating, comment, rated_at) "
         "VALUES (%s, %s, 'Shaun Jones', 'not_a_fit', 'too broad', '2026-11-10T09:00:00Z')", (LAST_WEEK, SECOND))


@pytest.fixture(scope="module")
def site() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-top10-ratings-test-{os.getpid()}"
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
def browser(site: None) -> Iterator[Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        b = p.chromium.launch()
        yield b
        b.close()


def as_person(browser: Any, name: str) -> Any:
    page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
    page.goto(f"{WEB}/calls", wait_until="load", timeout=120_000)
    menu = page.locator(".topbar details.account")
    menu.locator("summary").click()
    menu.locator("form.choose-viewer button[name=viewer]", has_text=name).click()
    page.wait_for_timeout(1500)
    return page


def home_row(page: Any, call_id: str) -> Any:
    page.goto(f"{WEB}/", wait_until="load", timeout=120_000)
    page.wait_for_timeout(1200)
    return page.locator(f"#top-panel-calls tr[data-call-id='{call_id}']")


def rate(page: Any, row: Any, rating: str, why: str = "") -> None:
    if why:
        row.locator("details.pick-why > summary").click()
        row.locator("details.pick-why textarea[name=comment]").fill(why)
    row.locator(f".pick-form button[name=rating][value={rating}]").click()
    page.wait_for_url(re.compile(r"[?&](notice|error)="), timeout=30_000)
    page.wait_for_timeout(600)


def ratings_of(call_id: str, week: str = WEEK) -> list[tuple[str, str, str | None]]:
    return [(r[0], r[1], r[2]) for r in _sql("SELECT rated_by, rating, comment FROM top10_ratings WHERE week_of = %s AND call_id = %s "
                                             "ORDER BY rated_by", (week, call_id))]


def test_two_people_rate_a_pick_on_home_apart_from_their_decisions(browser: Any) -> None:
    from playwright.sync_api import expect

    david = as_person(browser, "David Wood")
    row = home_row(david, FIRST)
    rate(david, row, "good_pick", "fits our C2 work")
    row = david.locator(f"#top-panel-calls tr[data-call-id='{FIRST}']")
    expect(row.locator(".pick-outcome")).to_have_text("Saved")
    expect(row.locator(".pick-form button[name=rating][value=good_pick]")).to_have_attribute("aria-pressed", "true")
    assert ratings_of(FIRST) == [("David Wood", "good_pick", "fits our C2 work")]
    assert _sql("SELECT COUNT(*) FROM decisions WHERE call_id = %s", (FIRST,)) == [(0,)]   # a rating is not a decision
    assert _sql("SELECT human_status FROM calls WHERE id = %s", (FIRST,)) == [(None,)]

    shaun = as_person(browser, "Shaun Jones")
    row = home_row(shaun, FIRST)
    expect(row.locator(".pick-others")).to_contain_text("David Wood")
    expect(row.locator(".pick-others")).to_contain_text("Good pick")
    expect(row.locator(".pick-others")).to_contain_text("fits our C2 work")
    rate(shaun, row, "not_a_fit")
    assert ratings_of(FIRST) == [("David Wood", "good_pick", "fits our C2 work"), ("Shaun Jones", "not_a_fit", None)]


def test_rating_again_replaces_your_rating_for_that_week(browser: Any) -> None:
    from playwright.sync_api import expect

    david = as_person(browser, "David Wood")
    row = home_row(david, SECOND)
    rate(david, row, "good_pick")
    row = home_row(david, SECOND)   # a reload keeps it
    expect(row.locator(".pick-form button[name=rating][value=good_pick]")).to_have_attribute("aria-pressed", "true")
    rate(david, row, "unsure", "depends on the teaming partner")
    assert ratings_of(SECOND) == [("David Wood", "unsure", "depends on the teaming partner")]
    assert ratings_of(SECOND, LAST_WEEK) == [("Shaun Jones", "not_a_fit", "too broad")]   # last week's stays its own


def test_top_10_reviews_lists_each_week_with_every_rating_and_whether_people_agree(browser: Any) -> None:
    from playwright.sync_api import expect

    page = as_person(browser, "David Wood")
    page.goto(f"{WEB}/top10-reviews", wait_until="load", timeout=120_000)
    expect(page.locator(".view-cards a[aria-current=page]")).to_contain_text("Top 10 reviews")
    weeks = page.locator("section.review-week")
    expect(weeks).to_have_count(2)
    now = weeks.nth(0)
    expect(now).to_contain_text("week of 16 Nov")
    first = now.locator(f"tr[data-call-id='{FIRST}']")
    expect(first.locator("td[data-person='David Wood']")).to_contain_text("Good pick")
    expect(first.locator("td[data-person='David Wood']")).to_contain_text("fits our C2 work")
    expect(first.locator("td[data-person='Shaun Jones']")).to_contain_text("Not a fit")
    expect(first.locator("td.agreement")).to_contain_text("split")
    before = weeks.nth(1)
    expect(before).to_contain_text("week of 9 Nov")
    expect(before.locator(f"tr[data-call-id='{SECOND}'] td[data-person='Shaun Jones']")).to_contain_text("too broad")
    page.reload(wait_until="load")
    expect(page.locator("section.review-week").nth(0).locator(f"tr[data-call-id='{FIRST}'] td.agreement")).to_contain_text("split")
