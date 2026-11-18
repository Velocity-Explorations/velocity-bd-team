"""Tuning on Fit ratings (Task 3 of the 9 Nov call, 18 Nov 2026), in a browser against a throwaway Postgres, never the live
ledger.

Find narrows every section to what matches, as the typing stops, and Sort orders the rows; both stay in the address. A
rating says Saving... then Saved, and a save that fails says why at its row. The Scans card puts the last scan's time on
a line of its own, so a narrow card never breaks the date at a hyphen.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine container
(Docker) and the built dashboard on port 8009 against it, and remove both at the end.
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
DB_PORT, WEB_PORT = 54335, 8009
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones"
KEYWORDS = {"autonomy": ("good", 12), "radar": ("never", 3), "data": ("neutral", 40)}   # rating, calls that hold it


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
    lq.save_tag_list([("Software", "work", "building or modernizing software"), ("Hardware", "work", "building physical equipment")])
    run_id = lq.start_run("sam_gov")
    for word, (_, calls) in KEYWORDS.items():
        for n in range(calls):
            call_id = f"fit-{word}-{n:02d}"
            lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": f"A call about {word} {n}", "type": "Solicitation",
                            "url": f"https://example.invalid/{call_id}", "description": "Seeded for the Fit ratings tests."}, run_id)
            _sql("UPDATE calls SET filter_result = 'kept', matched_keywords = %s WHERE id = %s", (f'["{word}"]', call_id))
    lq.finish_run(run_id, "completed", {"found": 55})
    for word, (rating, _) in KEYWORDS.items():
        _sql("INSERT INTO fit_ratings (key, section, name, rating, note, loaded_at) VALUES (%s, 'keyword', %s, %s, NULL, %s)",
             (f"keyword.{word}", word, rating, "2026-11-18T00:00:00Z"))


@pytest.fixture(scope="module")
def site() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-fit-tuning-test-{os.getpid()}"
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
    page.goto(f"{WEB}/fit", wait_until="load", timeout=120_000)
    menu = page.locator(".topbar details.account")
    menu.locator("summary").click()
    menu.locator("form.choose-viewer button[name=viewer]", has_text=name).click()
    page.wait_for_timeout(1500)


def keyword_rows(page: Any) -> list[str]:
    return [t.strip() for t in page.locator("section#keyword tbody tr .fit-name").all_inner_texts()]


def rating_of(word: str) -> str | None:
    (row,) = _sql("SELECT rating FROM fit_ratings WHERE key = %s", (f"keyword.{word}",))
    return row[0]


def test_find_narrows_the_sections_and_sort_orders_the_rows(page: Any) -> None:
    from playwright.sync_api import expect

    log_in(page, "David Wood")
    page.goto(f"{WEB}/fit?section=keyword", wait_until="load", timeout=120_000)
    page.wait_for_timeout(1000)
    assert sorted(keyword_rows(page)) == ["autonomy", "data", "radar"]
    page.locator(".fit-find input[type=search]").fill("rad")
    page.wait_for_url(re.compile(r"[?&]q=rad"), timeout=10_000)
    expect(page.locator("section#keyword tbody tr .fit-name")).to_have_count(1)
    assert keyword_rows(page) == ["radar"]
    assert "section=keyword" in page.url   # the open section stays
    expect(page.locator(".fit-tabs [role=tab]", has_text="Capability area")).to_contain_text("0")   # nothing there matches

    page.locator(".fit-find input[type=search]").fill("")
    page.wait_for_url(lambda url: "q=" not in url, timeout=10_000)
    page.locator(".fit-find select[name=sort]").select_option("calls")
    page.wait_for_url(re.compile(r"[?&]sort=calls"), timeout=10_000)
    page.wait_for_timeout(500)
    assert keyword_rows(page) == ["data", "autonomy", "radar"]   # 40, 12 and 3 calls
    page.locator(".fit-find select[name=sort]").select_option("rating")
    page.wait_for_url(re.compile(r"[?&]sort=rating"), timeout=10_000)
    page.wait_for_timeout(500)
    assert keyword_rows(page) == ["autonomy", "data", "radar"]   # Good, Neutral, Never
    page.reload(wait_until="load")   # a link or a reload keeps the order
    assert keyword_rows(page) == ["autonomy", "data", "radar"]


def test_a_rating_says_saving_then_saved(page: Any) -> None:
    from playwright.sync_api import expect

    log_in(page, "David Wood")
    page.goto(f"{WEB}/fit?section=keyword", wait_until="load", timeout=120_000)
    page.wait_for_timeout(1000)
    row = page.locator("section#keyword tbody tr", has=page.locator(".fit-name", has_text="data"))
    slider = row.locator("input[type=range].fit-slider")
    slider.focus()
    page.keyboard.press("ArrowRight")   # Neutral to Good: each step saves
    expect(row.locator(".fit-slider-state")).to_have_text("Saved", timeout=10_000)
    assert rating_of("data") == "good"


def test_a_save_that_fails_says_why_at_its_row(page: Any) -> None:
    from playwright.sync_api import expect

    log_in(page, "David Wood")
    page.goto(f"{WEB}/fit?section=keyword", wait_until="load", timeout=120_000)
    page.wait_for_timeout(1000)
    row = page.locator("section#keyword tbody tr", has=page.locator(".fit-name", has_text="autonomy"))
    # A form the server cannot take: a rating it does not know, as a stale page could send.
    row.locator("form.fit-form").evaluate("f => { f.querySelector('input[name=rating]').value = 'bogus'; f.requestSubmit(); }")
    page.wait_for_url(re.compile(r"[?&]error="), timeout=10_000)
    page.wait_for_timeout(800)
    row = page.locator("section#keyword tbody tr", has=page.locator(".fit-name", has_text="autonomy"))
    error = row.locator(".fit-slider-error")
    expect(error).to_contain_text("Choose a rating for autonomy")
    assert row.evaluate("el => { const r = el.getBoundingClientRect(); return r.top < window.innerHeight && r.bottom > 0; }")
    assert rating_of("autonomy") == "good"   # nothing changed


def test_the_scans_card_never_breaks_its_date(page: Any) -> None:
    page.set_viewport_size({"width": 1024, "height": 800})
    log_in(page, "David Wood")
    page.goto(f"{WEB}/fit", wait_until="load", timeout=120_000)
    line = page.locator(".view-cards a", has_text="Scans").locator(".vt-card__description")
    text = line.inner_text()
    assert text.startswith("last completed\n"), text
    date = text.split("\n", 1)[1]
    assert re.match(r"\d{4}-\d{2}-\d{2} ", date), date
    # The date sits on one line: a range around it has a single box.
    boxes = line.evaluate("""el => { const node = [...el.childNodes].find((n) => n.nodeType === 3);
      const at = node.textContent.indexOf('\\n') + 1; const range = document.createRange();
      range.setStart(node, at); range.setEnd(node, at + 10); return range.getClientRects().length; }""")
    assert boxes == 1
