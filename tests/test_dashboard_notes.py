"""A call's note box saves itself (David, 16 Nov 2026), driven in a browser against a throwaway Postgres, never the
live ledger: a note typed under Add a note is stored under the person signed in a second after the typing stops or on
leaving the box, with no decision needed and without touching the call's decision; editing the box edits that note,
emptying it takes it away, and a decision chosen while the box holds the note keeps one line for it.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine container
(Docker) and the built dashboard on port 8004 against it, and remove both at the end.
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
DB_PORT, WEB_PORT = 54331, 8004
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones,Lisa Hall"

PURSUED = "notes-pursued"     # the team pursued it; David said not relevant
EDITED = "notes-edited"       # undecided: the box is typed into, edited and emptied
DECIDED = "notes-decided"     # undecided: a note typed, then a decision chosen
NO_VOTE = "notes-no-vote"     # a note from someone who has not voted
SIGNED_OUT = "notes-signed-out"


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


def _db_ready() -> bool:
    import psycopg

    with psycopg.connect(DB_URL, connect_timeout=3) as conn:
        return conn.execute("SELECT 1").fetchone() == (1,)


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
                    "description": "Seeded for the note box tests."}, run_id)


def seed() -> None:
    _call(PURSUED, "Note box pursued call")
    lq.set_human(PURSUED, "not_relevant", "David Wood")
    lq.set_human(PURSUED, "pursue", "Shaun Jones")   # the call's decision is Shaun's Pursue; David's own is Not relevant
    _call(EDITED, "Note box edited call")
    _call(DECIDED, "Note box decided call")
    _call(NO_VOTE, "Note box call nobody voted on")
    lq.append_note(NO_VOTE, "worth a look once the topic posts", "Lisa Hall")
    _call(SIGNED_OUT, "Note box call while signed out")


@pytest.fixture(scope="module")
def site() -> Iterator[None]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-notes-test-{os.getpid()}"
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


def row_of(page: Any, call_id: str, title: str) -> Any:
    page.goto(f"{WEB}/calls?q={urllib.request.quote(title)}", wait_until="load", timeout=120_000)
    page.wait_for_timeout(2000)   # the note box is a client control; give it time to hydrate
    return page.locator(f"tr[data-call-id='{call_id}']")


def note_box(row: Any) -> Any:
    row.locator("details.add-note > summary").click()
    return row.locator("textarea[name=note]")


def call_of(call_id: str) -> dict[str, Any]:
    with ledger():
        call = lq.get_call(call_id)
    assert call is not None
    return call


def lines_of(call_id: str) -> list[str]:
    return [line for line in (call_of(call_id).get("human_notes") or "").split("\n") if line]


def decisions_of(call_id: str) -> list[tuple[str, str, str | None]]:
    import psycopg

    with psycopg.connect(DB_URL) as conn:
        rows = conn.execute("SELECT decided_by, status, note FROM decisions WHERE call_id = %s ORDER BY id", (call_id,)).fetchall()
    return [(r[0], r[1], r[2]) for r in rows]


def settles(check: Any, seconds: float = 15) -> None:
    """Waits for the ledger to show what a save should have written."""
    deadline = time.time() + seconds
    while time.time() < deadline:
        if check():
            return
        time.sleep(0.3)
    assert check()


STAMPED = re.compile(r"^\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z) David Wood\] (.*)$")


def test_a_note_saves_itself_under_the_person_signed_in_and_leaves_the_decision_alone(page: Any) -> None:
    log_in(page, "David Wood")
    row = row_of(page, PURSUED, "Note box pursued call")
    box = note_box(row)
    box.fill("We have never focused on identity management")
    settles(lambda: len(lines_of(PURSUED)) == 1)
    (line,) = lines_of(PURSUED)
    match = STAMPED.match(line)
    assert match and match.group(2) == "We have never focused on identity management", line
    assert row.locator(".call-note-state").inner_text() == "Note saved"
    call = call_of(PURSUED)
    assert (call["human_status"], call["human_by"]) == ("pursue", "Shaun Jones")
    assert decisions_of(PURSUED) == [("David Wood", "not_relevant", None), ("Shaun Jones", "pursue", None)]


def test_editing_the_box_edits_its_note_and_emptying_it_takes_the_note_away(page: Any) -> None:
    log_in(page, "David Wood")
    row = row_of(page, EDITED, "Note box edited call")
    box = note_box(row)
    box.fill("first thoughts")
    settles(lambda: len(lines_of(EDITED)) == 1)
    first = STAMPED.match(lines_of(EDITED)[0])
    assert first
    box.fill("first thoughts, then a second")
    settles(lambda: lines_of(EDITED)[0].endswith("then a second"))
    (line,) = lines_of(EDITED)
    edited = STAMPED.match(line)
    assert edited and edited.group(1) == first.group(1) and edited.group(2) == "first thoughts, then a second"
    box.fill("")
    box.blur()
    settles(lambda: lines_of(EDITED) == [])
    assert decisions_of(EDITED) == []


def test_a_decision_chosen_with_a_typed_note_keeps_one_line_for_it(page: Any) -> None:
    log_in(page, "David Wood")
    row = row_of(page, DECIDED, "Note box decided call")
    box = note_box(row)
    box.fill("call the program manager first")
    row.locator("details.decide-menu > summary").click()   # leaving the box saves the note
    row.locator(".decide-menu button[name=status][value=pursue]").click()
    page.wait_for_url(re.compile(r"[?&](notice|error)="), timeout=30_000)
    call = call_of(DECIDED)
    assert (call["human_status"], call["human_by"]) == ("pursue", "David Wood")
    (line,) = lines_of(DECIDED)
    match = STAMPED.match(line)
    assert match and match.group(2) == "call the program manager first", line
    assert decisions_of(DECIDED) == [("David Wood", "pursue", "call the program manager first")]


def test_notes_from_someone_with_no_vote_open_from_votes(page: Any) -> None:
    log_in(page, "David Wood")
    row = row_of(page, NO_VOTE, "Note box call nobody voted on")
    votes = row.locator("td.votes-cell .people-votes")
    assert "Notes from Lisa Hall" in votes.inner_text()
    votes.locator(".note-btn").click()
    panel = page.locator(f"tr.panel-row[data-for='{NO_VOTE}']:has-text('worth a look once the topic posts')")
    panel.wait_for(state="visible", timeout=5_000)


def test_signed_out_the_box_says_to_log_in_and_saves_nothing(page: Any) -> None:
    row = row_of(page, SIGNED_OUT, "Note box call while signed out")
    box = note_box(row)
    box.fill("anonymous")
    box.blur()
    state = row.locator(".call-note-state")
    state.filter(has_text="Log in").wait_for(timeout=10_000)
    assert lines_of(SIGNED_OUT) == []
