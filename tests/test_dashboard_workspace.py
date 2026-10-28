"""The proposal workspace (PW1 to PW25, PRO-580), driven in a browser against a throwaway Postgres seeded with
pursuits, never the live ledger: these tests press Approve, Ask for changes, No-go and the rest.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine
container (Docker) and the built dashboard on port 8002 against it, and remove both at the end.
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
DB_PORT, WEB_PORT = 54329, 8002
WEB = f"http://localhost:{WEB_PORT}"
DB_URL = f"postgresql://postgres@127.0.0.1:{DB_PORT}/postgres"
PEOPLE = "David Wood,Shaun Jones,Lisa Hall"


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


# ------------------------------------------------------------------------------ the seed

def _call(call_id: str, title: str) -> None:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": title, "type": "Sources Sought", "department": "DEPT OF THE ARMY",
                    "due_date": "2027-01-15", "url": f"https://example.invalid/{call_id}",
                    "description": "Seeded for the workspace tests."}, run_id)
    lq.set_human(call_id, "pursue", "David Wood")


def _saved(pursuit_id: int, step: str, summary: str = "- Found the notice\n- Attachments to fetch") -> dict[str, Any]:
    """The worker takes the queued step and saves it ready."""
    row = lq.claim_next_step()
    assert row is not None and row["pursuit_id"] == pursuit_id and row["step"] == step, row
    assert lq.finish_step(row["id"], summary=summary, cost_usd=0.05,
                          files=[{"name": f"{step} document", "local": f"pursuit-{pursuit_id}/{step}.md",
                                  "word": f"pursuit-{pursuit_id}/{step}.docx"}],
                          content={"document": f"# {step}\nThe full text.", "question": f"Is the {step} right?"})
    return lq.get_step(row["id"])


def _pursuit(call_id: str, title: str, **options: Any) -> int:
    _call(call_id, title)
    return lq.start_pursuit(call_id, "David Wood", format="White paper", collaborators=["Shaun Jones"], **options)


def seed() -> dict[str, int]:
    found: dict[str, int] = {}
    for key in ("approve", "stale", "changes", "material"):
        found[key] = _pursuit(f"ws-{key}", f"Workspace {key}")
        _saved(found[key], "discovery")
    found["failed"] = _pursuit("ws-failed", "Workspace failed")
    row = lq.claim_next_step()
    lq.fail_step(row["id"], "discovery: the model refused this request", cost_usd=0.02)
    found["blocked"] = _pursuit("ws-blocked", "Workspace blocked")
    row = lq.claim_next_step()
    lq.block_step(row["id"], "budget reached", cost_usd=200.0)
    found["working"] = _pursuit("ws-working", "Workspace working")
    lq.claim_next_step()
    found["nogo"] = _pursuit("ws-nogo", "Workspace no-go")
    lq.approve_step(_saved(found["nogo"], "discovery")["id"], "David Wood")
    _saved(found["nogo"], "summary")
    found["gate"] = _pursuit("ws-gate", "Workspace gate")
    for step in ("discovery", "summary", "alignment", "requirements"):
        lq.approve_step(_saved(found["gate"], step)["id"], "David Wood")
    _saved(found["gate"], "go_no_go")
    lq.save_checklist(found["gate"], [
        {"part": "registrations", "text": "SAM.gov registration active", "source": "per notice", "owner": "David Wood", "done": True},
        {"part": "inputs", "text": "Key personnel bios", "owner": "Shaun Jones", "due_date": "2027-01-05", "done": False},
    ], "requirements")
    _call("ws-undrafted", "Workspace with no draft")
    return found


@pytest.fixture(scope="module")
def site() -> Iterator[dict[str, int]]:
    if not (DASHBOARD / ".next" / "BUILD_ID").exists():
        pytest.skip("run `npm run build` in dashboard/ first")
    name = f"bd-workspace-test-{os.getpid()}"
    subprocess.run(["docker", "run", "-d", "--rm", "--name", name, "-p", f"127.0.0.1:{DB_PORT}:5432",
                    "-e", "POSTGRES_HOST_AUTH_METHOD=trust", "postgres:17-alpine"], check=True, capture_output=True, timeout=180)
    try:
        _wait(_db_ready, "The throwaway Postgres")
        migrate.apply(DB_URL)
        with ledger():
            found = seed()
        env = {**os.environ, "DATABASE_URL": DB_URL, "DASHBOARD_USERS": PEOPLE, "DASHBOARD_IAP_AUDIENCE": "",
               "DASHBOARD_USER_HEADER": "", "DASHBOARD_QUEUE": ""}
        server = subprocess.Popen(["node", str(Path("node_modules") / "next" / "dist" / "bin" / "next"), "start", "--port", str(WEB_PORT)],
                                  cwd=DASHBOARD, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            _wait(_web_ready, "The dashboard on port 8002")
            yield found
        finally:
            _kill(server)
    finally:
        subprocess.run(["docker", "stop", name], capture_output=True, timeout=120)


@pytest.fixture()
def page(site: dict[str, int]) -> Iterator[Any]:
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser.new_context(viewport={"width": 1440, "height": 900}).new_page()
        browser.close()


def open_workspace(page: Any, call_id: str, step: str = "") -> None:
    page.goto(f"{WEB}/proposals/{call_id}" + (f"?step={step}" if step else ""), wait_until="load", timeout=120_000)
    page.wait_for_timeout(300)


def log_in(page: Any, name: str) -> None:
    page.goto(f"{WEB}/proposals", wait_until="load", timeout=120_000)
    menu = page.locator(".topbar details.account")
    menu.locator("summary").click()
    menu.locator("form.choose-viewer button[name=viewer]", has_text=name).click()
    page.wait_for_timeout(1500)


def step_row(step_id: int) -> dict[str, Any]:
    with ledger():
        return lq.get_step(step_id)


def steps_of(pursuit_id: int) -> list[tuple[str, int, str]]:
    with ledger():
        return [(s["step"], s["attempt"], s["state"]) for s in lq.pursuit_steps(pursuit_id)]


def notice(page: Any) -> str:
    return page.locator(".notice").first.inner_text()


def act(page: Any, button: Any) -> None:
    """Press a workspace action and wait for its redirect, which carries a notice or an error."""
    button.click()
    page.wait_for_url(re.compile(r"[?&](notice|error)="), timeout=30_000)


# ------------------------------------------------------------------------------ the tests

def test_the_page_shows_the_header_the_strip_the_steps_and_the_open_card(page: Any, site: dict[str, int]) -> None:
    open_workspace(page, "ws-approve")
    assert page.locator("h1.ws-title").inner_text() == "Workspace approve"
    facts = page.locator(".ws-facts").inner_text()
    for expected in ("SAM.gov", "White paper", "Owner: David Wood", "Working with: Shaun Jones",
                     "User approval required: every step", "Spent $0.05 of $200.00"):
        assert expected in facts, expected
    assert "Qualifying" in page.locator(".ws-crumb").inner_text()
    stages = [t.split("\n") for t in page.locator(".ws-strip li").all_inner_texts()]
    assert [s[0].strip().lower() for s in stages] == ["qualify", "plan", "draft", "review", "finalize", "submit"]
    assert page.locator(".ws-stage.now .ws-stage-name").inner_text().lower() == "qualify"
    steps = page.locator(".ws-steps li")
    assert steps.count() == 11
    assert "ready" in steps.first.inner_text() and "waiting" in steps.nth(1).inner_text()
    card = page.locator(".ws-card")
    assert "STEP 1 OF 9 · DISCOVERY" in card.locator(".ws-band").inner_text().upper()
    assert "Found the notice" in card.locator(".ws-points").inner_text()
    assert "discovery document" in card.locator(".ws-files").inner_text()
    assert "Is the discovery right?" in card.locator(".ws-question").inner_text()
    # Nobody is logged in, so the card says who decides and offers no approval.
    assert "Waiting on David Wood, the owner" in card.inner_text()
    assert card.get_by_role("button", name="Approve and continue").count() == 0


def test_the_owner_approves_and_the_next_step_waits_for_the_worker(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-approve")
    act(page, page.locator(".ws-card").get_by_role("button", name="Approve and continue"))
    assert "Approved. Opportunity summary is queued for the worker." in notice(page)
    assert steps_of(site["approve"]) == [("discovery", 1, "approved"), ("summary", 1, "queued")]
    assert "done" in page.locator(".ws-steps li").first.inner_text()


def test_a_page_left_open_while_the_step_changed_saves_nothing(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-stale")
    with ledger():
        first = lq.pursuit_steps(site["stale"])[0]
        assert lq.ask_changes(first["id"], "David Wood", "Changed in another tab")
    act(page, page.locator(".ws-card").get_by_role("button", name="Approve and continue"))
    assert "This step changed since the page loaded" in page.locator(".notice").first.inner_text()
    assert steps_of(site["stale"]) == [("discovery", 1, "changes_asked"), ("discovery", 2, "queued")]


def test_ask_for_changes_queues_the_step_again_with_the_note(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-changes")
    card = page.locator(".ws-card")
    card.locator("summary", has_text="Ask for changes").click()
    card.locator("textarea[name=note]").first.fill("Check the DSIP topic page too")
    act(page, card.get_by_role("button", name="Ask for changes").last)
    assert "Asked for changes" in notice(page)
    assert steps_of(site["changes"]) == [("discovery", 1, "changes_asked"), ("discovery", 2, "queued")]
    with ledger():
        redo = lq.pursuit_steps(site["changes"])[-1]
    assert redo["request_note"] == "Check the DSIP topic page too"


def test_a_failed_step_says_why_and_retries(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-failed")
    card = page.locator(".ws-card")
    assert "This step failed: discovery: the model refused this request" in card.inner_text()
    act(page, card.get_by_role("button", name="Retry"))
    assert steps_of(site["failed"]) == [("discovery", 1, "failed"), ("discovery", 2, "queued")]


def test_budget_reached_offers_raise_the_cap_and_requeues_the_step(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-blocked")
    card = page.locator(".ws-card")
    assert "Budget reached: $200.00 spent of the $200.00 cap." in card.inner_text()
    assert card.get_by_role("button", name="Retry").count() == 0
    card.locator("input[name=budget]").fill("300")
    act(page, card.get_by_role("button", name="Raise the cap"))
    assert "The cap is $300.00. The step is queued again for the worker." in notice(page)
    with ledger():
        assert lq.get_pursuit(site["blocked"])["budget_usd"] == 300
    assert steps_of(site["blocked"]) == [("discovery", 1, "blocked"), ("discovery", 2, "queued")]


def test_a_working_step_says_so_and_asks_nothing(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-working")
    card = page.locator(".ws-card")
    assert "working" in card.locator(".ws-band").inner_text()
    assert "Claude is working on this step and asks nothing until it is saved." in card.inner_text()
    assert card.locator(".ws-call").count() == 0


def test_people_working_with_the_owner_add_material_and_tick_items_but_do_not_decide(page: Any, site: dict[str, int]) -> None:
    log_in(page, "Shaun Jones")
    open_workspace(page, "ws-material")
    card = page.locator(".ws-card")
    assert card.get_by_role("button", name="Approve and continue").count() == 0
    card.locator("summary", has_text="Add material").click()
    card.locator("textarea[name=material]").fill("The parent BAA: https://example.invalid/baa.pdf")
    act(page, card.get_by_role("button", name="Add material").last)
    assert "Material added." in notice(page)
    with ledger():
        events = lq.pursuit_events(site["material"])
    assert (events[-1]["kind"], events[-1]["who"], events[-1]["text"]) == ("material", "Shaun Jones",
                                                                           "The parent BAA: https://example.invalid/baa.pdf")
    open_workspace(page, "ws-gate")
    page.get_by_role("button", name="Checklist, 1 of 2 done").click()
    act(page, page.locator("#ws-checklist").get_by_role("button", name="Tick: Key personnel bios"))
    with ledger():
        items = lq.checklist(site["gate"])
    assert [(i["text"], i["done"], i["done_by"]) for i in items] == [
        ("SAM.gov registration active", 1, "worker"), ("Key personnel bios", 1, "Shaun Jones")]


def test_the_gate_takes_go_with_conditions_and_each_joins_the_checklist(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-gate")
    card = page.locator(".ws-card")
    assert "GATE · GO OR NO-GO" in card.locator(".ws-band").inner_text().upper()
    assert card.get_by_role("button", name="Approve and continue").count() == 0
    card.locator("summary", has_text="Go with conditions").click()
    card.locator("textarea[name=conditions]").fill("Sign a teaming partner\nGet the cost inputs")
    act(page, card.get_by_role("button", name="Go with conditions").last)
    assert "Go with conditions recorded. Outline is queued for the worker." in notice(page)
    with ledger():
        gate = [s for s in lq.pursuit_steps(site["gate"]) if s["step"] == "go_no_go"][0]
        items = lq.checklist(site["gate"])
    assert (gate["state"], gate["decision"]) == ("approved", "go_with_conditions")
    assert [(i["text"], i["origin"], i["owner"]) for i in items if i["origin"] == "condition"] == [
        ("Sign a teaming partner", "condition", "David Wood"), ("Get the cost inputs", "condition", "David Wood")]
    assert steps_of(site["gate"])[-1] == ("outline", 1, "queued")


def test_stop_here_no_go_stops_the_draft_and_marks_the_call_not_relevant(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-nogo")
    card = page.locator(".ws-card")
    card.locator("summary", has_text="Stop here, no-go").click()
    card.locator(".ws-stop textarea[name=note]").fill("Hardware-heavy; a software topic would change the answer")
    act(page, card.get_by_role("button", name="Stop here, no-go").last)
    assert "No-go recorded, and the call is marked Not relevant" in notice(page)
    with ledger():
        assert lq.get_pursuit(site["nogo"])["state"] == "no_go"
        assert lq.get_call("ws-nogo")["human_status"] == "not_relevant"
    assert "No-go" in page.locator(".ws-crumb").inner_text()


def test_show_history_lists_what_happened(page: Any, site: dict[str, int]) -> None:
    open_workspace(page, "ws-approve")
    assert page.locator("#ws-history").is_hidden()
    page.get_by_role("button", name="Show history").click()
    history = page.locator("#ws-history")
    assert history.is_visible()
    assert "Started the draft: White paper, every step approved" in history.inner_text()


def test_a_call_without_a_draft_says_so_and_an_unknown_call_is_not_found(page: Any, site: dict[str, int]) -> None:
    open_workspace(page, "ws-undrafted")
    assert "This call has no draft yet." in page.locator("main").inner_text()
    response = page.goto(f"{WEB}/proposals/no-such-call", wait_until="load", timeout=120_000)
    assert response is not None and response.status == 404
