"""Each portal's newest scan on Scans (Task 6 of the 9 Nov call, 18 Nov 2026), in a browser against a throwaway Postgres,
never the live ledger.

One row per portal from its newest scan that wrote to the ledger (no dry runs, no calls added by hand), with what it
read and how many of this week's Top 10 came from it; a failure, nothing found, or no scan for over a week is flagged.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine container
(Docker) and the built dashboard on port 8013 against it, and remove both at the end.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest

from ledger import migrate
from ledger import queries as lq

pytestmark = pytest.mark.skipif(not os.environ.get("WORKSPACE_TESTS"),
                                reason="set WORKSPACE_TESTS=1 (needs Docker and a built dashboard)")

REPO = Path(__file__).resolve().parent.parent
DASHBOARD = REPO / "dashboard"
DB_PORT, WEB_PORT = 54338, 8013
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones"


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


def _ago(days: float) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _run(portal: str, component: str, status: str, counts: dict[str, int] | None, days_ago: float, dry: bool = False) -> int:
    run_id = lq.start_run(portal, dry_run=dry, component=component)
    lq.finish_run(run_id, status, counts, error="boom" if status == "error" else None)
    _sql("UPDATE runs SET started_at = %s, finished_at = %s WHERE id = %s", (_ago(days_ago), _ago(days_ago - 0.01), run_id))
    return run_id


def _call(call_id: str, portal: str, run_id: int) -> None:
    lq.upsert_call({"id": call_id, "portal": portal, "title": f"Call {call_id}", "type": "Solicitation",
                    "url": f"https://example.invalid/{call_id}", "description": "Seeded for the portal scan tests."}, run_id)


def seed() -> None:
    _run("SAM.gov", "sam_gov", "error", None, 4)   # an older failure, not the newest
    sam = _run("SAM.gov", "sam_gov", "completed", {"fetched": 290, "filtered": 90, "reviewed": 75, "new": 15}, 1)
    _run("APFIT", "apfit", "completed", {"fetched": 0, "filtered": 0, "reviewed": 0, "new": 0}, 1)
    diu = _run("DIU", "diu", "error", None, 1)
    _run("DIU", "diu", "completed", {"fetched": 9, "filtered": 1, "reviewed": 1, "new": 1}, 0.5, dry=True)   # a dry run: left out
    _run("NSTXL", "nstxl", "completed", {"fetched": 16, "filtered": 0, "reviewed": 0, "new": 0}, 10)
    _run("dsip", "dsip_manual", "completed", {"added": 3}, 0.2)   # calls added by hand: left out
    for call_id, portal, run_id in (("scan-sam-1", "SAM.gov", sam), ("scan-sam-2", "SAM.gov", sam), ("scan-diu-1", "DIU", diu)):
        _call(call_id, portal, run_id)
    lq.save_brief("2026-11-16", None, {"top": [{"id": c, "title": f"Call {c}", "portal": p} for c, p in
                                               (("scan-sam-1", "SAM.gov"), ("scan-sam-2", "SAM.gov"), ("scan-diu-1", "DIU"))],
                                       "watch": [], "ranked_by": "seeded"}, "tests")


@pytest.fixture(scope="module")
def site() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-portal-scans-test-{os.getpid()}"
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


def row(page: Any, portal: str) -> Any:
    return page.locator(f"section.portal-scans tr[data-portal='{portal}']")


def test_scans_show_each_portals_newest_scan_with_what_to_look_at(page: Any) -> None:
    from playwright.sync_api import expect

    page.goto(f"{WEB}/runs", wait_until="load", timeout=120_000)
    rows = page.locator("section.portal-scans tbody tr")
    expect(rows).to_have_count(4)   # SAM.gov, APFIT, DIU, NSTXL: no dry run, no calls added by hand
    assert [r.get_attribute("data-portal") for r in rows.all()] == ["APFIT", "DIU", "NSTXL", "SAM.gov"]
    sam = row(page, "SAM.gov")
    assert [t.strip() for t in sam.locator("td.num").all_inner_texts()] == ["290", "90", "75", "15", "2"]   # and 2 in the Top 10
    expect(sam.locator("td.look-at")).to_have_text("nothing")   # the newest is fine; the older failure is not it
    expect(row(page, "APFIT").locator("td.look-at")).to_have_text("found nothing")
    expect(row(page, "DIU").locator("td.look-at")).to_have_text("failed")
    expect(row(page, "DIU").locator("td.num").last).to_have_text("1")
    expect(row(page, "NSTXL").locator("td.look-at")).to_have_text("no scan for 10 days")


def test_scan_problems_keeps_to_the_problem_runs(page: Any) -> None:
    from playwright.sync_api import expect

    page.goto(f"{WEB}/runs?view=problems", wait_until="load", timeout=120_000)
    expect(page.locator("section.portal-scans")).to_have_count(0)
