"""Home's Top 10 explained (Task 9 of the 9 Nov call, 18 Nov 2026), in a browser against a throwaway Postgres, never the
live ledger.

The line above the Top 10 says when the Monday brief picked it, from how many portals' scans, which calls, and the rule
the brief stored for ranking them. A pick that has closed since leaves the list (David, 18 Nov 2026), and the ranks close
up. Calls' Top 10 lists the calls in Home's order.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine container
(Docker) and the built dashboard on port 8014 against it, and remove both at the end.
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
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest

from ledger import migrate
from ledger import queries as lq

pytestmark = pytest.mark.skipif(not os.environ.get("WORKSPACE_TESTS"),
                                reason="set WORKSPACE_TESTS=1 (needs Docker and a built dashboard)")

REPO = Path(__file__).resolve().parent.parent
DASHBOARD = REPO / "dashboard"
DB_PORT, WEB_PORT = 54339, 8014
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones"
RULE = "the seeded rule for this brief"
ORDER = ["line-first", "line-closed", "line-third"]   # the brief's order


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


def seed() -> None:
    sam = lq.start_run("SAM.gov", component="sam_gov")
    lq.finish_run(sam, "completed", {"fetched": 3})
    diu = lq.start_run("DIU", component="diu")
    lq.finish_run(diu, "completed", {"fetched": 1})
    dry = lq.start_run("NSTXL", dry_run=True, component="nstxl")   # a dry run is not a scan the Top 10 draws from
    lq.finish_run(dry, "completed", {"fetched": 5})
    for call_id, days in (("line-first", 20), ("line-closed", -1), ("line-third", 40)):
        lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": f"Call {call_id}", "type": "Solicitation",
                        "due_date": (date.today() + timedelta(days=days)).isoformat(), "url": f"https://example.invalid/{call_id}",
                        "description": "Seeded for the Top 10 line tests."}, sam)
        _sql("UPDATE calls SET filter_result = 'kept', ai_verdict = 'yes', ai_reasoning = 'Seeded.' WHERE id = %s", (call_id,))
    lq.save_brief("2026-11-16", None, {"top": [{"id": c, "title": f"Call {c}", "portal": "SAM.gov"} for c in ORDER], "watch": [],
                                       "ranked_by": RULE}, "tests")
    _sql("UPDATE briefs SET created_at = '2026-11-16T16:00:17Z' WHERE portal IS NULL")


@pytest.fixture(scope="module")
def site() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-top10-line-test-{os.getpid()}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{DB_PORT}:5432",
                    "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:17-alpine"], check=True, capture_output=True, timeout=180)
    try:
        _wait(lambda: _sql("SELECT 1") == [(1,)], "The throwaway Postgres")
        migrate.apply(DB_URL)
        with ledger():
            seed()
        env = {**os.environ, "DATABASE_URL": DB_URL, "DASHBOARD_USERS": PEOPLE, "DASHBOARD_IAP_AUDIENCE": "",
               "DASHBOARD_USER_HEADER": "", "DASHBOARD_QUEUE": "", "AUTH_GOOGLE_ID": "", "AUTH_GOOGLE_SECRET": "", "AUTH_SECRET": "",
               "DASHBOARD_CACHE_SECONDS": "0", "DASHBOARD_DB_MAX": "3", "DASHBOARD_TIMEZONE": "America/Denver"}
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
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{WEB}/calls", wait_until="load", timeout=120_000)
        menu = page.locator(".topbar details.account")
        menu.locator("summary").click()
        menu.locator("form.choose-viewer button[name=viewer]", has_text="David Wood").click()
        page.wait_for_timeout(1500)
        yield page
        browser.close()


def test_the_top_10_line_says_when_it_was_picked_from_what_and_by_which_rule(page: Any) -> None:
    page.goto(f"{WEB}/", wait_until="load", timeout=120_000)
    text = page.locator("section.top-ten").inner_text()
    assert re.search(r"Picked 2026-11-16 \d{2}:\d{2} \w+ by the Monday brief, from the open calls across 2 portals", text), text[:400]
    assert f"Ranked by {RULE}." in text
    assert "Forecasts, announcements and umbrellas are on the next tab." in text


def test_a_pick_that_has_closed_since_leaves_the_top_10(page: Any) -> None:
    page.goto(f"{WEB}/", wait_until="load", timeout=120_000)
    assert page.locator("#top-panel-calls tr[data-call-id='line-closed']").count() == 0
    assert "a pick that has closed since leaves the list" in page.locator("section.top-ten").inner_text()


def test_calls_top_10_lists_the_picks_in_homes_order(page: Any) -> None:
    page.goto(f"{WEB}/", wait_until="load", timeout=120_000)
    home = [r.get_attribute("data-call-id") for r in page.locator("#top-panel-calls tbody tr[data-call-id]").all()]
    assert [t.strip() for t in page.locator("#top-panel-calls tbody td.rank").all_inner_texts()] == ["1", "2"]
    page.goto(f"{WEB}/review?view=top10", wait_until="load", timeout=120_000)
    calls = [r.get_attribute("data-call-id") for r in page.locator("table.calls-table tbody tr[data-call-id]").all()]
    open_picks = [c for c in ORDER if c != "line-closed"]   # the closed pick has left both lists
    assert home == open_picks
    assert calls == open_picks
