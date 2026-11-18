"""Why this score (Task 4 of the 9 Nov call, 18 Nov 2026), in a browser against a throwaway Postgres, never the live ledger.

A call's reasons panel says why it scored what it did, from what the scoring stored: the score and band, each part
review/fit.py rated, and the keywords the filter matched; for a call in this week's Top 10, how the Top 10's rule ranked
it; then both judges' reasons. Home's Top 10 shows Grok's reason beside Claude's, and its rows open that panel.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine container
(Docker) and the built dashboard on port 8011 against it, and remove both at the end.
"""
from __future__ import annotations

import json
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
DB_PORT, WEB_PORT = 54336, 8011
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones"

TOP = "why-top"       # this week's Top 10, number 1
OTHER = "why-other"   # scored, not in the Top 10
PARTS = ["Primary focus Software: Core", "Type RFI: Good", "Customer USAF: Core", "Keyword communications: Core"]


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


def _scored(call_id: str, title: str, score: int, band: str, parts: list[str], due_in_days: int) -> None:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": title, "type": "Sources Sought", "department": "DEPT OF THE AIR FORCE",
                    "due_date": (date.today() + timedelta(days=due_in_days)).isoformat(), "url": f"https://example.invalid/{call_id}",
                    "description": "Seeded for the Why this score tests."}, run_id)
    _sql("UPDATE calls SET filter_result = 'kept', ai_verdict = 'yes', ai_reasoning = %s, fit_score = %s, fit_band = %s, fit_why = %s, "
         "matched_keywords = %s WHERE id = %s",
         (f"Claude says {title} is software for the Air Force.", score, band, json.dumps(parts),
          json.dumps(["information", "communications", "information"]), call_id))
    for judge, reason in (("claude", f"Claude says {title} is software for the Air Force."), ("grok", f"Grok says {title} fits on communications.")):
        _sql("INSERT INTO judgments (call_id, judge, model, verdict, reasoning, rated_at) VALUES (%s, %s, 'test', 'yes', %s, %s)",
             (call_id, judge, reason, "2026-11-16T00:00:00Z"))


def seed() -> None:
    _scored(TOP, "Why top call", 89, "strong", PARTS, 20)
    _scored(OTHER, "Why other call", 55, "possible", ["Primary focus Software: Core", "Customer Navy: Neutral"], 120)
    lq.save_brief("2026-11-16", None, {"top": [{"id": TOP, "title": "Why top call", "portal": "SAM.gov"}], "watch": [],
                                       "ranked_by": "seeded"}, "tests")


@pytest.fixture(scope="module")
def site() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-why-score-test-{os.getpid()}"
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
    page.goto(f"{WEB}/calls", wait_until="load", timeout=120_000)
    menu = page.locator(".topbar details.account")
    menu.locator("summary").click()
    menu.locator("form.choose-viewer button[name=viewer]", has_text=name).click()
    page.wait_for_timeout(1500)


def test_a_top_10_call_opened_from_home_shows_why_it_scored_and_how_it_ranked(page: Any) -> None:
    from playwright.sync_api import expect

    log_in(page, "David Wood")
    page.goto(f"{WEB}/", wait_until="load", timeout=120_000)
    page.wait_for_timeout(1200)
    page.locator(f"tr[data-call-id='{TOP}'] td.call").click()   # a Home row opens Calls, Top 10, with its reasons open
    page.wait_for_url(re.compile(r"/review\?view=top10&focus="), timeout=30_000)
    panel = page.locator(f"tr.panel-row[data-for='{TOP}']")
    expect(panel).to_be_visible(timeout=10_000)
    why = panel.locator(".panel-why")
    expect(why).to_contain_text("Why this score")
    expect(why.locator(".why-headline")).to_have_text("Fit 89, strong")
    assert [t.strip() for t in why.locator(".why-parts li").all_inner_texts()] == PARTS
    expect(why).to_contain_text("Keywords the filter matched: information, communications.")
    rank = why.locator(".why-rank")
    expect(rank).to_contain_text("#1 in this week's Top 10.")
    assert re.search(r"Yes from both judges; closes in \d+ days, within the 60 days that rank first; then its fit score, 89\.",
                     rank.inner_text()), rank.inner_text()
    expect(panel).to_contain_text("Claude says Why top call is software for the Air Force.")
    expect(panel).to_contain_text("Grok says Why top call fits on communications.")


def test_homes_top_10_shows_grok_reason_beside_claudes(page: Any) -> None:
    from playwright.sync_api import expect

    log_in(page, "David Wood")
    page.goto(f"{WEB}/", wait_until="load", timeout=120_000)
    cell = page.locator(f"tr[data-call-id='{TOP}'] td.reason").last
    expect(cell).to_contain_text("Claude says Why top call is software for the Air Force.")
    expect(cell).to_contain_text("Grok says Why top call fits on communications.")
    expect(page.locator("#top-panel-calls thead th", has_text="Judges' reasons")).to_have_count(1)
    # The fit badge stays inside its column: since the Fit column came on 6 Nov, "55 possible" ran into Claude's badge.
    _sql("UPDATE calls SET fit_score = 69, fit_band = 'possible' WHERE id = %s", (TOP,))
    page.reload(wait_until="load")
    fit = page.locator(f"tr[data-call-id='{TOP}'] td.fit")
    inside = fit.evaluate("td => { const b = td.querySelector('.badge').getBoundingClientRect(); const c = td.getBoundingClientRect(); "
                          "return b.right <= c.right && b.left >= c.left; }")
    _sql("UPDATE calls SET fit_score = 89, fit_band = 'strong' WHERE id = %s", (TOP,))
    assert inside, "the fit badge runs out of its column"


def test_a_call_outside_the_top_10_shows_why_it_scored_without_a_rank(page: Any) -> None:
    from playwright.sync_api import expect

    log_in(page, "David Wood")
    page.goto(f"{WEB}/calls?q=Why%20other%20call", wait_until="load", timeout=120_000)
    page.wait_for_timeout(1200)
    page.locator(f"button[data-panel='reasons-{OTHER}']").first.click()
    why = page.locator(f"tr.panel-row[data-for='{OTHER}'] .panel-why")
    expect(why).to_be_visible(timeout=5_000)
    expect(why.locator(".why-headline")).to_have_text("Fit 55, possible")
    expect(why.locator(".why-rank")).to_have_count(0)


def test_homes_top_10_headers_line_up_with_their_cells(page: Any) -> None:
    """Every header is a table cell over its column. On 18 Nov the Claude and Grok headers took a class another style made a
    flex box, which stacked them in one column and shifted every header after them."""
    log_in(page, "David Wood")
    for width in (1024, 1440):
        page.set_viewport_size({"width": width, "height": 900})
        page.goto(f"{WEB}/", wait_until="load", timeout=120_000)
        page.wait_for_timeout(800)
        found = page.evaluate("""() => {
          const table = document.querySelector('#top-panel-calls table');
          const shown = (el) => getComputedStyle(el).display !== 'none';
          const heads = [...table.querySelectorAll('thead th')].filter(shown);
          const cells = [...table.querySelector('tbody tr').children].filter(shown);
          return { displays: heads.map((th) => getComputedStyle(th).display),
                   pairs: heads.map((th, i) => [Math.round(th.getBoundingClientRect().left), Math.round(cells[i] ? cells[i].getBoundingClientRect().left : -1)]) };
        }""")
        assert set(found["displays"]) == {"table-cell"}, (width, found["displays"])
        assert all(head == cell for head, cell in found["pairs"]), (width, found["pairs"])
