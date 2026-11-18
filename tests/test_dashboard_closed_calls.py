"""Closed calls stay in the ledger but leave the open lists (David, 18 Nov 2026), in a browser against a throwaway
Postgres, never the live ledger.

A call is closed when its portal flagged it closed or its deadline has passed. A closed call leaves this week's Top 10,
Calls' Top 10, Needs review and the Open filter. It stays in the ledger and on All calls, where the Closed filter finds
it, ranks renumber around it, and the Top 10's line says a closed pick leaves the list.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine container
(Docker) and the built dashboard on port 8015 against it, and remove both at the end.
"""
from __future__ import annotations

import json
import os
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
DB_PORT, WEB_PORT = 54340, 8015
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones"

PAST = "closed-past-due"      # its deadline passed yesterday; no portal flag
OPEN = "closed-still-open"    # due in 10 days
FLAGGED = "closed-flagged"    # due in 30 days, but its portal flagged it closed
NO_DUE = "closed-no-deadline" # no deadline at all: open
BRIEF = [PAST, OPEN, FLAGGED, NO_DUE]   # the Monday brief's order


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
    run_id = lq.start_run("SAM.gov", component="sam_gov")
    lq.finish_run(run_id, "completed", {"fetched": 4})
    for call_id, days in ((PAST, -1), (OPEN, 10), (FLAGGED, 30), (NO_DUE, None)):
        due = (date.today() + timedelta(days=days)).isoformat() if days is not None else None
        lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": f"Call {call_id}", "type": "Solicitation", "due_date": due,
                        "url": f"https://example.invalid/{call_id}", "description": "Seeded for the closed call tests."}, run_id)
        _sql("UPDATE calls SET filter_result = 'kept', ai_verdict = 'yes', ai_reasoning = 'Seeded.' WHERE id = %s", (call_id,))
    _sql("UPDATE calls SET extra = %s WHERE id = %s", (json.dumps({"sam_closed": True}), FLAGGED))
    lq.save_brief("2026-11-16", None, {"top": [{"id": c, "title": f"Call {c}", "portal": "SAM.gov"} for c in BRIEF], "watch": [],
                                       "ranked_by": "seeded"}, "tests")


@pytest.fixture(scope="module")
def site() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-closed-calls-test-{os.getpid()}"
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
        page = browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        page.goto(f"{WEB}/calls", wait_until="load", timeout=120_000)
        menu = page.locator(".topbar details.account")
        menu.locator("summary").click()
        menu.locator("form.choose-viewer button[name=viewer]", has_text="David Wood").click()
        page.wait_for_timeout(1500)
        yield page
        browser.close()


def listed(page: Any, path: str, rows: str = "table.calls-table tbody tr[data-call-id]") -> list[str]:
    page.goto(f"{WEB}{path}", wait_until="load", timeout=120_000)
    return [r.get_attribute("data-call-id") for r in page.locator(rows).all()]


def test_closed_picks_leave_this_weeks_top_10_and_the_ranks_close_up(page: Any) -> None:
    assert listed(page, "/", "#top-panel-calls tbody tr[data-call-id]") == [OPEN, NO_DUE]
    assert [t.strip() for t in page.locator("#top-panel-calls tbody td.rank").all_inner_texts()] == ["1", "2"]
    assert "a pick that has closed since leaves the list" in page.locator("section.top-ten").inner_text()
    assert listed(page, "/review?view=top10") == [OPEN, NO_DUE]


def test_closed_calls_leave_needs_review_and_the_open_filter(page: Any) -> None:
    assert sorted(listed(page, "/review")) == sorted([OPEN, NO_DUE])
    assert sorted(listed(page, "/calls?state=open")) == sorted([OPEN, NO_DUE])
    assert sorted(listed(page, "/calls?state=closed")) == sorted([PAST, FLAGGED])


def test_closed_calls_stay_in_the_ledger_and_on_all_calls(page: Any) -> None:
    assert sorted(listed(page, "/calls")) == sorted(BRIEF)
    assert sorted(r[0] for r in _sql("SELECT id FROM calls")) == sorted(BRIEF)
