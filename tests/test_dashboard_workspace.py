"""The proposal workspace (PW1 to PW25, PRO-580), driven in a browser against a throwaway Postgres seeded with
pursuits, never the live ledger: these tests press Approve, Ask for changes, No-go and the rest.

Opt in with WORKSPACE_TESTS=1 after `npm run build` in dashboard/. The tests start a postgres:17-alpine
container (Docker) and the built dashboard on port 8002 against it, and remove both at the end.
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


def _saved(pursuit_id: int, step: str, summary: str = "- Found the notice\n- Attachments to fetch",
           content: dict[str, Any] | None = None, tasks: dict[str, str] | None = None) -> dict[str, Any]:
    """The worker takes the queued step and saves it ready, with what its screen shows."""
    row = lq.claim_next_step()
    assert row is not None and row["pursuit_id"] == pursuit_id and row["step"] == step, row
    if tasks:
        lq.set_task_states(row["id"], tasks)
    assert lq.finish_step(row["id"], summary=summary, cost_usd=0.05,
                          files=[{"name": f"{step} document", "local": f"pursuit-{pursuit_id}/{step}.md",
                                  "word": f"pursuit-{pursuit_id}/{step}.docx"}],
                          content={"document": f"# {step}\nThe full text.", "question": f"Is the {step} right?", **(content or {})})
    return lq.get_step(row["id"])


def _through(pursuit_id: int, last: str) -> None:
    """Every step before `last` saved and approved, the gate as Go."""
    for step in lq.STEPS[:lq.STEPS.index(last)]:
        lq.approve_step(_saved(pursuit_id, step)["id"], "David Wood", decision="go" if step == "go_no_go" else None)


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
    for key in ("rev-view", "rev-decide", "rev-stale", "rev-check"):   # before seed_screens, which leaves a step queued
        found[key] = _reviews(key)
    seed_end(found)
    seed_library(found)
    seed_screens(found)
    return found


TASKS = {"call_page": "for_owner", "attachments": "for_owner", "parent_instructions": "done", "key_facts": "done",
         "past_work": "done", "clashes": "done", "record": "done", "summary": "done"}
ANGLE = "Lead with Echo C2 at Cobra Gold, and name a teaming partner for Army past performance"
BRIEF = {"fit": "Moderate fit", "fit_reason": "C2 matches; no Army past performance yet.", "win_themes": ["Echo C2 offline"],
         "gaps": [{"gap": "No Army past performance", "mitigation": "Team with a partner who has it"}],
         "effort": "30 days to the deadline; the milestones fit.", "recommendation": "go_with_conditions",
         "recommendation_text": "Go once a partner signs.", "conditions": ["Sign a teaming partner", "Confirm the cost inputs"]}


def seed_screens(found: dict[str, int]) -> None:
    """A pursuit at each step with a screen of its own (PW6 to PW11)."""
    found["discovery"] = _pursuit("ws-discovery", "Workspace discovery")
    _saved(found["discovery"], "discovery", tasks=TASKS, content={
        "tasks": TASKS, "owner_fetch": ["The call page on SAM.gov, for amendments"],
        "result_expected": {"date": "2027-04-15", "source": "default, 90 days after the deadline"}})
    found["summary"] = _pursuit("ws-summary", "Workspace summary")
    _through(found["summary"], "summary")
    _saved(found["summary"], "summary", content={"document": "# Opportunity summary\n\nThe Army wants edge AI decision aids.\n\nMore."})
    for key in ("align", "align-new"):
        found[key] = _pursuit(f"ws-{key}", f"Workspace {key}", direction="Lead with Echo C2")
        _through(found[key], "alignment")
        _saved(found[key], "alignment", content={
            "verdict": "Strong on C2, one gap", "angle": ANGLE, "comparison": "Both lead with Echo C2",
            "direction": "Lead with Echo C2",
            "points": [{"tag": "fits", "text": "Army C2 work matches Echo C2", "source": "Claude and Grok"},
                       {"tag": "risk", "text": "No Army past performance", "source": "Grok"}]})
    found["req"] = _pursuit("ws-req", "Workspace requirements")
    _through(found["req"], "requirements")
    _saved(found["req"], "requirements", content={
        "requirements": {"volumes": "One white paper", "page_limit": "10 pages, 12 point, PDF", "evaluation": "Technical merit",
                         "eligibility": "Small business", "keywords": "Listed in the file"}, "submit_by": "2027-01-14"})
    lq.save_checklist(found["req"], [
        {"part": "documents", "text": "White paper, 10 pages, PDF", "owner": "Claude", "done": True},
        {"part": "inputs", "text": "Company profile figures", "owner": "David Wood", "done": False}], "requirements")
    found["brief"] = _pursuit("ws-brief", "Workspace brief")
    _through(found["brief"], "go_no_go")
    _saved(found["brief"], "go_no_go", content=BRIEF)
    found["outline"] = _pursuit("ws-outline", "Workspace outline", direction="Lead with Echo C2",
                                builds_on=[{"id": "d1", "name": "C2 prototype white paper"}])
    _through(found["outline"], "outline")
    _saved(found["outline"], "outline", content={
        "page_limit": "10 pages", "unmapped_criteria": ["Cost realism"],
        "sections": [{"title": "1. Technical Approach", "criteria": ["Technical merit"], "share": "5 pages",
                      "evidence": ["Cobra Gold 2026"]}]})
    found["draft"] = _pursuit("ws-draft", "Workspace draft")
    _through(found["draft"], "draft")
    _saved(found["draft"], "draft", content={"words": 3240, "placeholders": {"PERSON WRITES": 1, "NEEDS INPUT": 60,
                                                                            "NEEDS EVIDENCE": 0, "other": 0},
                                             "slop": "Not ready: 1 PERSON WRITES, 60 NEEDS INPUT; band clean (provisional)"})
    found["people"] = _pursuit("ws-people", "Workspace people")


# A made-up scan in the scanner's JSON shape: the family names, fixes and matched words are examples, not the scanner's own.
SCAN_TEXT = "\n".join([
    "# White paper", "Sure thing, here it is.", "[PERSON WRITES: the opening]", "This is not just X; a, b and c.", "",
    "## 2. Technical approach", "We use wordtwo and wordthree.", "The partner is [NEEDS INPUT: the partner's name].",
    "It not only this but also that, with wordone.", "## 3. Work plan", "Then d, e and f.",
    "The objective of this topic is to develop it.", "Hours: [NEEDS INPUT: hours per task]"])


def _family(label: str, tier: str, hits: int, points: float, fix: str) -> dict[str, Any]:
    return {"label": label, "tier": tier, "hits": hits, "distinct": hits, "per_1k": hits * 0.5, "fired": points > 0,
            "points": points, "fix": fix}


def _finding(family: str, tier: str, line: int, column: int, match: str, exempt: str = "") -> dict[str, Any]:
    return {"rule": "example", "family": family, "tier": tier, "line": line, "column": column, "match": match, "text": match,
            "weight": 1, "term": False, "exempt": exempt, "paragraph": 1, "start": 0, "end": 1}


SCAN_REPORT = {
    "source": "draft_v2.md", "profile": "proposal", "channel": "document", "words": 2140, "sentences": 150, "band": "light",
    "confidence": "full", "points": 9, "discourse_fired": 2, "residue_label": "tool residue", "percentile": None,
    "thresholds": {"light": 2, "revise": 4, "heavy": 7, "calibrated": False, "n": 0},
    "families": {
        "contrast": _family("contrast frames", "discourse", 2, 3, "Say what the thing does."),
        "greet": _family("chatbot greetings (example)", "discourse", 1, 0, "Start with the answer."),
        "lex_a": _family("GPT era words (example)", "lexicon", 1, 1, "Use the plain word."),
        "lex_b": _family("Claude era words (example)", "lexicon", 1, 1, "Use the plain word."),
        "triads": _family("lists of three", "surface", 2, 0.5, "Keep the two that carry information."),
        "residue": _family("tool residue", "residue", 0, 0, "Delete it."),
        "sourcing": _family("chatbot link tags (example)", "sourcing", 0, 0, "Strip it."),
        "house": _family("house rules (example CLAUDE.md)", "house", 0, 0, "Rewrite it."),
        "prop_overlap": _family("sentence copied from the solicitation", "proposal", 1, 0, "Answer it in your own words."),
        "prop_open_item": _family("open placeholders", "proposal", 3, 0, "Fill it in."),
    },
    "findings": [
        _finding("greet", "discourse", 2, 1, "Sure thing"),
        _finding("prop_open_item", "proposal", 3, 1, "[PERSON WRITES: the opening]"),
        _finding("contrast", "discourse", 4, 1, "This is not just X"),
        _finding("triads", "surface", 4, 21, "a, b and c"),
        _finding("lex_b", "lexicon", 7, 8, "wordtwo"),
        _finding("lex_b", "lexicon", 7, 20, "wordthree", "the solicitation uses this term"),
        _finding("prop_open_item", "proposal", 8, 16, "[NEEDS INPUT: the partner's name]"),
        _finding("contrast", "discourse", 9, 4, "not only this but also that"),
        _finding("lex_a", "lexicon", 9, 40, "wordone"),
        _finding("triads", "surface", 11, 6, "d, e and f"),
        _finding("prop_overlap", "proposal", 12, 1, "The objective of this topic"),
        _finding("prop_open_item", "proposal", 13, 8, "[NEEDS INPUT: hours per task]"),
    ],
    "hot_paragraphs": [{"lines": [8, 11], "findings": 3, "families": ["contrast frames", "GPT era words (example)"]}],
}
VERDICT = "Not ready: 1 PERSON WRITES, 2 NEEDS INPUT; band light (provisional)"
PASSES = [
    {"pass": 1, "code": "evaluator_1", "reviewer": "External evaluator", "status": "done", "changes": 2, "dropped": 0, "points": [],
     "ratings": [{"criterion": "Technical merit", "rating": "Good", "strengths": "A clear plan", "weaknesses": "No baseline"},
                 {"criterion": "Key people", "rating": "Marginal", "strengths": "", "weaknesses": "Two bios missing"}]},
    {"pass": 2, "code": "evaluator_2", "reviewer": "Second independent evaluator", "status": "done", "changes": 1, "dropped": 0,
     "points": [], "ratings": [{"criterion": "Technical merit", "rating": "Acceptable", "strengths": "", "weaknesses": ""}]},
    {"pass": 3, "code": "leadership", "reviewer": "Velocity leadership", "status": "done", "changes": 1, "dropped": 0, "points": [],
     "ratings": []},
]


def _reviews(key: str) -> int:
    """A pursuit at Reviews: the three reviewers' changes to decide, and the scan of Draft v2 (PW12, PW20)."""
    pursuit_id = _pursuit(f"ws-{key}", f"Workspace {key}")
    _through(pursuit_id, "reviews")
    row = lq.claim_next_step()
    assert row is not None and row["step"] == "reviews", row
    lq.add_step_changes(row["id"], "evaluator_1", [
        {"section": "1. Technical approach", "before": "We use wordtwo.", "after": "We use the C2 prototype.", "reason": "Name the system"},
        {"section": "2. Plan", "before": "The partner helps.", "after": "The partner leads tasks 3 and 4.", "reason": "Show the split"}])
    lq.add_step_changes(row["id"], "evaluator_2", [
        {"section": "3. Costs", "before": "Costs are low.", "after": "Costs are $150,000.", "reason": "Give the number"}])
    lq.add_step_changes(row["id"], "leadership", [
        {"section": "4. Transition", "before": "We will try.", "after": "We will deliver the Phase II plan.", "reason": "Commit"}])
    assert lq.finish_step(row["id"], summary="- External evaluator: 2 changes proposed", cost_usd=0.4,
                          files=[{"name": "Review 1, External evaluator", "local": f"pursuit-{pursuit_id}/review_1.md"}],
                          content={"document": "# Review 1", "passes": PASSES, "changes": 4,
                                   "question": "Here is what the reviews found, as changes to decide. Accept, reject or edit "
                                               "each, then approve the draft."})
    lq.save_slop_scan(pursuit_id, None, "draft_v2.md", SCAN_REPORT, verdict=VERDICT, ready=False, fixed_count=7, text=SCAN_TEXT)
    return pursuit_id


FINAL_TEXT = "\n".join(["# White paper", "", "Hours: [NEEDS INPUT: hours per task]", "", "Body."])
FINAL_CHECKS = [
    {"check": "Formatting check", "ok": True, "result": "done", "detail": "the formatting pass ran on the final version"},
    {"check": "Final compliance re-check", "ok": True, "result": "passed", "detail": "2 to check; the report is final_compliance.md"},
    {"check": "Placeholder sweep", "ok": False, "result": "1 left", "detail": "1 NEEDS INPUT, for David Wood"},
    {"check": "AI slop check, final pass", "ok": False, "result": "not ready",
     "detail": "Not ready: 1 NEEDS INPUT; band clean (provisional). Dash check passed: no en or em dashes"},
    {"check": "Submission package check", "ok": None, "result": "not run", "detail": "Runs once Drive is set up"},
    {"check": "Checklist updated", "ok": True, "result": "updated", "detail": "1 of 2 done; every open item has an owner and a date"},
    {"check": "Final version saved", "ok": True, "result": "saved", "detail": "draft_final.md and its Word file"},
]
SUBMIT_CONTENT = {
    "checks": [{"check": "Checklist", "ok": False, "detail": "1 item is still open"},
               {"check": "AI slop check", "ok": True, "detail": "Ready: band light (provisional)"}],
    "files": [{"file": "White paper (PDF)", "slot": "email attachment"}], "portal_steps": ["Email the PDF to the contracting officer"],
    "deadline": "2027-01-15, time not given", "call_page": "https://example.invalid/ws-sub-gate",
    "question": "Submit on the portal, then enter the confirmation number and the result expected by date, and choose Mark submitted."}


def _scan_final(pursuit_id: int, ready: bool) -> None:
    report = {"words": 900, "band": "clean", "confidence": "full", "points": 0, "thresholds": {"calibrated": False},
              "families": {}, "hot_paragraphs": [],
              "findings": [] if ready else [{"family": "prop_open_item", "tier": "proposal", "line": 3, "column": 8,
                                             "match": "[NEEDS INPUT: hours per task]", "exempt": ""}]}
    lq.save_slop_scan(pursuit_id, None, "draft_final.md", report, ready=ready, fixed_count=0,
                      verdict="Ready: band clean (provisional)" if ready else "Not ready: 1 NEEDS INPUT; band clean (provisional)",
                      text=FINAL_TEXT.replace("[NEEDS INPUT: hours per task]", "40 hours") if ready else FINAL_TEXT)


def _submitted(call_id: str, title: str, expected: str | None, **pursuit: Any) -> int:
    """A pursuit marked submitted, waiting on its result."""
    from ledger.db import q, tx

    pursuit_id = _pursuit(call_id, title)
    lq.claim_next_step()
    with tx() as conn:
        q(conn, "UPDATE pursuits SET state = 'submitted', current_step = 'submit', submitted_at = '2026-09-01T15:00:00Z', "
                "submitted_by = 'David Wood', confirmation_number = 'CONF-1', result_expected_by = ? WHERE id = ?", (expected, pursuit_id))
    lq.set_human(call_id, "submitted", "David Wood")
    return pursuit_id


def seed_end(found: dict[str, int]) -> None:
    """Pursuits at Final checks and the Submit gate, and calls waiting on a result (PW13, PW14, P4)."""
    found["fin-gate"] = _pursuit("ws-fin-gate", "Workspace final gate")
    _through(found["fin-gate"], "final")
    _saved(found["fin-gate"], "final", content={"checks": FINAL_CHECKS, "verdict": "Not ready: 1 NEEDS INPUT; band clean (provisional)",
                                                "placeholders": [{"kind": "NEEDS INPUT", "text": "[NEEDS INPUT: hours per task]",
                                                                  "line": 3, "section": "White paper"}]})
    _scan_final(found["fin-gate"], ready=False)
    for key in ("sub-gate", "sub-stale"):
        found[key] = _pursuit(f"ws-{key}", f"Workspace {key}")
        _through(found[key], "submit")
        _saved(found[key], "submit", content=SUBMIT_CONTENT)
    found["sw-late"] = _submitted("ws-sw-late", "Waiting late", "2026-09-30")
    found["sw-result"] = _submitted("ws-sw-result", "Waiting for a result", "2027-06-01")
    _call("ws-sw-outside", "Submitted outside the workspace")
    lq.set_human("ws-sw-outside", "submitted", "Shaun Jones")


FOLDER = "application/vnd.google-apps.folder"


def seed_library(found: dict[str, int]) -> None:
    """The Proposal Library's index, a worker that has run, a call to start, and a pursuit at its Outline (phase 6b)."""
    lq.worker_started(lq.WORKER)
    lq.save_drive_items([
        {"id": "lib-ve27", "name": "2026-03-17_vulcan-sof_vigilant-eagle-27", "mime": FOLDER,
         "path": "Submissions/2026-03-17_vulcan-sof_vigilant-eagle-27", "indexed_at": "2026-10-29T15:00:00Z"},
        {"id": "lib-bio", "name": "David Wood bio.docx", "mime": "application/msword", "path": "01 Company Reference/Bios/David Wood bio.docx",
         "indexed_at": "2026-10-29T15:00:00Z"}])
    _call("ws-start", "Workspace start with past work")
    found["outline-lib"] = _pursuit("ws-outline-lib", "Workspace outline library")
    _through(found["outline-lib"], "outline")
    _saved(found["outline-lib"], "outline", content={"sections": [{"title": "1. Approach", "criteria": ["Merit"], "evidence": []}]})


def pursuit_of(pursuit_id: int) -> dict[str, Any]:
    with ledger():
        return lq.get_pursuit(pursuit_id)


def changes_of(pursuit_id: int) -> list[tuple[str, str, str | None, str | None]]:
    with ledger():
        step = next(s for s in lq.pursuit_steps(pursuit_id) if s["step"] == "reviews")
        return [(c["section"], c["state"], c["decided_by"], c["edited_text"]) for c in lq.step_changes(step["id"])]


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


# --------------------------------------------------------------------- each step's own screen (PRO-581)

def test_discovery_lists_its_eight_tasks_and_what_is_left_to_fetch(page: Any, site: dict[str, int]) -> None:
    open_workspace(page, "ws-discovery")
    card = page.locator(".ws-card")
    assert card.locator(".ws-tasks li").count() == 8
    assert card.locator(".ws-progress").inner_text() == "6 of 8 done, 2 for you"
    assert "for you" in card.locator(".ws-tasks li").first.inner_text()
    assert "The call page on SAM.gov, for amendments" in card.inner_text()
    assert "Result expected by 2027-04-15" in card.inner_text()


def test_the_summary_shows_the_key_facts_and_continues_to_alignment(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-summary")
    card = page.locator(".ws-card")
    assert "The Army wants edge AI decision aids." in card.locator(".ws-lead").inner_text()
    rows = card.locator(".ws-rows").inner_text()
    assert "DEPT OF THE ARMY" in rows and "Sources Sought" in rows
    act(page, card.get_by_role("button", name="Continue to Alignment"))
    assert steps_of(site["summary"])[-2:] == [("summary", 1, "approved"), ("alignment", 1, "queued")]


def test_alignment_carries_claudes_angle_forward(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-align")
    card = page.locator(".ws-card")
    assert "Strong on C2, one gap" in card.locator(".ws-verdict").inner_text()
    assert [t.split("\n")[0] for t in card.locator(".ws-tagged li").all_inner_texts()] == ["fits", "risk"]
    assert "Lead with Echo C2" in card.locator(".ws-pair").inner_text() and ANGLE in card.locator(".ws-pair").inner_text()
    assert card.locator("input[value=keep]").is_checked()
    card.locator("input[value=claude]").check()
    act(page, card.get_by_role("button", name="Approve and continue"))
    with ledger():
        assert lq.get_pursuit(site["align"])["direction"] == ANGLE
        assert lq.pursuit_events(site["align"])[-2]["kind"] == "direction"


def test_alignment_takes_a_new_direction(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-align-new")
    card = page.locator(".ws-card")
    card.locator("input[value=new]").check()
    card.locator("textarea[name=direction]").fill("Lead with the offline demo and the Cobra Gold numbers")
    act(page, card.get_by_role("button", name="Approve and continue"))
    with ledger():
        assert lq.get_pursuit(site["align-new"])["direction"] == "Lead with the offline demo and the Cobra Gold numbers"


def test_requirements_show_their_rows_and_a_checklist_ticked_from_the_card(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-req")
    card = page.locator(".ws-card")
    rows = card.locator(".ws-rows").first.inner_text().lower()   # the labels are capitalised by the stylesheet
    for expected in ("volumes", "one white paper", "page limit and format", "10 pages, 12 point, pdf", "eligibility"):
        assert expected in rows, expected
    assert "submission checklist, 1 of 2 done" in card.inner_text().lower()
    act(page, card.get_by_role("button", name="Tick: Company profile figures"))
    with ledger():
        assert [i["done"] for i in lq.checklist(site["req"])] == [1, 1]


def test_the_gate_shows_the_brief_and_fills_in_claudes_conditions(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-brief")
    card = page.locator(".ws-card")
    brief = card.locator(".ws-subsection").inner_text()
    for expected in ("Moderate fit", "C2 matches; no Army past performance yet.", "Echo C2 offline", "No Army past performance.",
                     "Team with a partner who has it", "30 days to the deadline", "Go with conditions", "Go once a partner signs."):
        assert expected in brief, expected
    card.locator("summary", has_text="Go with conditions").click()
    assert card.locator("textarea[name=conditions]").input_value() == "Sign a teaming partner\nConfirm the cost inputs"


def test_the_outline_lists_its_sections_and_locks_the_direction_and_past_work_when_approved(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-outline")
    card = page.locator(".ws-card")
    assert "direction, last chance to change" in card.inner_text().lower()
    assert [c.inner_text() for c in card.locator(".ws-sections tbody tr td").all()] == [
        "1. Technical Approach", "Technical merit", "5 pages", "Cobra Gold 2026"]
    assert "No section answers: Cost realism" in card.inner_text()
    act(page, card.get_by_role("button", name="Remove C2 prototype white paper"))
    open_workspace(page, "ws-outline")          # a fresh page between actions, after the redirect's re-render
    card = page.locator(".ws-card")
    card.locator("input[name=add]").fill("Cobra Gold 2026 after-action report")
    act(page, card.locator("form", has=page.locator("input[name=add]")).get_by_role("button", name="Add", exact=True))
    open_workspace(page, "ws-outline")
    card = page.locator(".ws-card")
    card.locator("summary", has_text="Edit").click()
    card.locator("textarea[name=direction]").fill("Lead with the Cobra Gold results")
    act(page, card.get_by_role("button", name="Save the direction"))
    with ledger():
        pursuit = lq.get_pursuit(site["outline"])
    assert json.loads(pursuit["builds_on"]) == [{"id": None, "name": "Cobra Gold 2026 after-action report"}]
    assert pursuit["direction"] == "Lead with the Cobra Gold results"
    open_workspace(page, "ws-outline")
    act(page, page.locator(".ws-card").get_by_role("button", name="Approve and continue"))
    open_workspace(page, "ws-outline", "outline")
    card = page.locator(".ws-card")
    assert "last chance" not in card.inner_text().lower()
    assert card.locator("input[name=add]").count() == 0 and card.locator("summary", has_text="Edit").count() == 0


def test_the_first_draft_shows_its_size_and_what_is_left_to_fill(page: Any, site: dict[str, int]) -> None:
    open_workspace(page, "ws-draft")
    rows = page.locator(".ws-card .ws-rows").inner_text()
    assert "3,240" in rows and "1 PERSON WRITES, 60 NEEDS INPUT" in rows
    assert "Not ready: 1 PERSON WRITES, 60 NEEDS INPUT; band clean (provisional)" in rows
    assert page.locator(".ws-card .ws-rows a", has_text="See the latest result").get_attribute("href") == "?step=draft&view=slop"


def test_the_owner_changes_who_works_with_them(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-people")
    page.get_by_role("button", name="People").click()
    panel = page.locator("#ws-people")
    panel.get_by_label("Lisa Hall").check()
    act(page, panel.get_by_role("button", name="Save who works on it"))
    with ledger():
        assert json.loads(lq.get_pursuit(site["people"])["collaborators"]) == ["Shaun Jones", "Lisa Hall"]


# ------------------------------------------------------------------------------ Reviews and the AI slop check (phase 8b)

def test_reviews_lists_the_check_the_reviewers_their_ratings_and_each_change(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-rev-view", "reviews")
    card = page.locator(".ws-card")
    assert "STEP 8 OF 9 · REVIEWS" in card.locator(".ws-band").inner_text().upper()
    rows = card.locator(".ws-reviewers > li")
    assert rows.count() == 4
    first = rows.nth(0).inner_text()
    assert "AI slop check" in first and VERDICT in first and "automatic" in first
    external = rows.nth(1).inner_text()
    for expected in ("External evaluator", "Technical merit", "Good", "Key people", "Marginal", "2 changes, 2 to decide", "to decide"):
        assert expected in external, expected
    assert "Second evaluator" in rows.nth(2).inner_text() and "Acceptable" in rows.nth(2).inner_text()
    assert "does not rate the criteria" in rows.nth(3).inner_text()
    rows.nth(1).locator("summary", has_text="Strengths and weaknesses").click()
    assert "Two bios missing" in rows.nth(1).inner_text()
    change = card.locator("#changes-evaluator_1 .ws-change").first
    text = change.inner_text()
    for expected in ("1. Technical approach", "We use wordtwo.", "We use the C2 prototype.", "Name the system"):
        assert expected in text, expected
    for name in ("Accept", "Reject"):
        assert change.get_by_role("button", name=name, exact=True).count() == 1
    assert change.locator("summary", has_text="Edit").count() == 1
    # Approval waits until every change is decided (PW12).
    assert card.get_by_role("button", name="Approve and continue").is_disabled()
    assert "Decide every change first: 4 still to decide." in card.locator(".ws-call").inner_text()


def test_people_working_with_the_owner_see_the_changes_but_do_not_decide_them(page: Any, site: dict[str, int]) -> None:
    log_in(page, "Shaun Jones")
    open_workspace(page, "ws-rev-view", "reviews")
    card = page.locator(".ws-card")
    assert card.locator(".ws-change").count() == 4
    assert card.get_by_role("button", name="Accept", exact=True).count() == 0
    assert card.get_by_role("button", name="Accept all").count() == 0
    assert "Waiting on David Wood, the owner" in card.inner_text()


def test_the_owner_accepts_rejects_and_edits_each_change_then_approves(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-rev-decide", "reviews")
    changes = page.locator(".ws-card .ws-change")
    act(page, changes.nth(0).get_by_role("button", name="Accept", exact=True))
    assert "Accepted the change to 1. Technical approach." in notice(page)
    assert re.search(r"#change-\d+$", page.url)
    open_workspace(page, "ws-rev-decide", "reviews")   # a clean address, so act() waits for the next notice
    act(page, page.locator(".ws-card .ws-change").nth(1).get_by_role("button", name="Reject", exact=True))
    assert "Rejected the change to 2. Plan." in notice(page)
    open_workspace(page, "ws-rev-decide", "reviews")   # a clean address, so act() waits for the next notice
    act(page, page.locator(".ws-card .ws-change").nth(1).get_by_role("button", name="Undo"))
    assert "The change to 2. Plan is back to decide." in notice(page)
    open_workspace(page, "ws-rev-decide", "reviews")   # a clean address, so act() waits for the next notice
    act(page, page.locator(".ws-card .ws-change").nth(1).get_by_role("button", name="Reject", exact=True))
    open_workspace(page, "ws-rev-decide", "reviews")   # a clean address, so act() waits for the next notice
    third = page.locator(".ws-card .ws-change").nth(2)
    third.locator("summary", has_text="Edit").click()
    third.locator("textarea[name=edited_text]").fill("Costs are $150,000 over nine months.")
    act(page, third.get_by_role("button", name="Save your version"))
    assert "Edited the change to 3. Costs." in notice(page)
    open_workspace(page, "ws-rev-decide", "reviews")   # a clean address, so act() waits for the next notice
    act(page, page.locator("#changes-leadership").get_by_role("button", name="Accept all"))
    assert "Velocity leadership: accepted 1 change." in notice(page)
    assert changes_of(site["rev-decide"]) == [
        ("1. Technical approach", "accepted", "David Wood", None), ("2. Plan", "rejected", "David Wood", None),
        ("3. Costs", "edited", "David Wood", "Costs are $150,000 over nine months."), ("4. Transition", "accepted", "David Wood", None)]
    open_workspace(page, "ws-rev-decide", "reviews")   # a clean address, so act() waits for the next notice
    card = page.locator(".ws-card")
    assert "your version" in card.locator(".ws-change").nth(2).inner_text().lower()
    assert "Accepted by David Wood" in card.locator(".ws-change").nth(0).inner_text()
    act(page, card.get_by_role("button", name="Approve and continue"))
    assert "Approved with 2 accepted, 1 edited, 1 rejected. Final checks is queued for the worker." in notice(page)
    assert steps_of(site["rev-decide"])[-2:] == [("reviews", 1, "approved"), ("final", 1, "queued")]
    page.get_by_role("button", name="Show history").click()
    assert "Reviews approved: 2 accepted, 1 edited, 1 rejected" in page.locator("#ws-history").inner_text()


def test_a_decision_from_a_page_left_open_saves_nothing(page: Any, site: dict[str, int]) -> None:
    from ledger.db import q, tx

    log_in(page, "David Wood")
    open_workspace(page, "ws-rev-stale", "reviews")
    with ledger():
        step = next(s for s in lq.pursuit_steps(site["rev-stale"]) if s["step"] == "reviews")
        first, *others = lq.step_changes(step["id"])
        assert lq.decide_change(first["id"], "David Wood", "rejected")
    act(page, page.locator(".ws-card .ws-change").first.get_by_role("button", name="Accept", exact=True))
    assert "That change was decided already" in page.locator(".notice").first.inner_text()
    assert changes_of(site["rev-stale"])[0][1] == "rejected"
    # The page saw every change decided, then one came back to decide elsewhere: Approve refuses (PW12).
    with ledger():
        for change in others:
            assert lq.decide_change(change["id"], "David Wood", "accepted")
    open_workspace(page, "ws-rev-stale", "reviews")
    with ledger(), tx() as conn:
        q(conn, "UPDATE step_changes SET state = 'proposed', decided_by = NULL, decided_at = NULL WHERE id = ?", (others[0]["id"],))
    act(page, page.locator(".ws-card").get_by_role("button", name="Approve and continue"))
    assert "Decide every change first: 1 still to decide." in page.locator(".notice").first.inner_text()
    assert steps_of(site["rev-stale"])[-1] == ("reviews", 1, "ready")


def test_the_slop_check_result_shows_the_verdict_what_is_open_and_what_to_fix(page: Any, site: dict[str, int]) -> None:
    open_workspace(page, "ws-rev-view", "reviews")
    page.locator(".ws-reviewers a", has_text="See the result").click()
    page.wait_for_url(re.compile(r"view=slop"))
    card = page.locator(".ws-card")
    assert "STEP 8 OF 9 · REVIEWS · AI SLOP CHECK" in card.locator(".ws-band").inner_text().upper()
    assert "not ready" in card.locator(".ws-band .badge").inner_text().lower()
    box = card.locator(".ws-verdict-box").inner_text()
    for expected in (VERDICT, "light", "9 points", "Confidence: normal, 2,140 words", "on Draft v2", "provisional until they are calibrated"):
        assert expected in box, expected
    assert "Fixed on its own before this scan: 7" in card.locator(".ws-fixed").inner_text()
    placeholders = card.locator("[aria-label='Open placeholders']").inner_text()
    assert "Open placeholders, 3".lower() in placeholders.lower()
    assert "White paper. [PERSON WRITES: the opening]" in placeholders and "2. Technical approach. [NEEDS INPUT" in placeholders
    hot = card.locator("[aria-label='Paragraphs to revise first']").inner_text()
    assert "2. Technical approach" in hot and "3 findings: contrast frames, overused words" in hot and "Lines 8 to 11" in hot
    families = card.locator("[aria-label='Findings by family'] .ws-family-head strong").all_inner_texts()
    assert families == ["Contrast frames", "Overused words", "Lists of three", "Greetings"]
    found = card.locator("[aria-label='Findings by family']").inner_text()
    assert "Say what the thing does." in found and "Tool residue: none · Tracking parameters: none · House rules: none" in found
    faults = card.locator("[aria-label='Proposal faults']").inner_text()
    assert "Sentence copied from the solicitation" in faults and "These do not count toward the band." in faults
    assert "1 finding was left out for that reason" in faults
    # Patterns and fixes only (PW23): no model or chatbot named, and nothing about who wrote the text.
    text = card.inner_text()
    for banned in ("GPT era", "Claude era", "chatbot", "written by AI", "AI-generated", "probability", "likely AI"):
        assert banned.lower() not in text.lower(), banned


def test_a_line_link_opens_the_scanned_text_beside_the_list(page: Any, site: dict[str, int]) -> None:
    page.goto(f"{WEB}/proposals/ws-rev-view?step=reviews&view=slop", wait_until="load", timeout=120_000)
    card = page.locator(".ws-card")
    card.locator("[aria-label='Open placeholders'] a", has_text="Line 8").click()
    page.wait_for_url(re.compile(r"lines=8#p-8$"))
    aside = page.locator(".ws-slop-text")
    assert "draft v2, line 8" in aside.locator("h3").inner_text().lower()
    hit = aside.locator("li.hit")
    assert hit.count() == 1 and "The partner is [NEEDS INPUT: the partner's name]." in hit.inner_text()
    assert "NEEDS INPUT, open" in hit.inner_text()
    card.locator("[aria-label='Paragraphs to revise first'] a", has_text="Lines 8 to 11").click()
    page.wait_for_url(re.compile(r"lines=8-11#h-1$"))
    assert page.locator(".ws-slop-text li.hit").count() == 4
    page.locator(".ws-slop-text a", has_text="Close").click()
    page.wait_for_url(re.compile(r"view=slop$"))
    assert page.locator(".ws-slop-text").count() == 0


SLOP_CHECK = f"{WEB}/proposals/ws-rev-check?step=reviews&view=slop"


def test_check_again_queues_a_scan_and_shows_its_state(page: Any, site: dict[str, int]) -> None:
    log_in(page, "Shaun Jones")   # working with the owner: Check again decides nothing
    page.goto(SLOP_CHECK, wait_until="load", timeout=120_000)
    with ledger():
        queued = lq.queue_job("slop_scan", site["rev-check"], None, "David Wood")
    act(page, page.locator(".ws-card").get_by_role("button", name="Check again"))
    assert "Check again is already waiting for the worker." in page.locator(".notice").first.inner_text()
    assert "queued" in page.locator(".ws-card .ws-notice.tone-info").inner_text()
    assert page.locator(".ws-card").get_by_role("button", name="Check again").is_disabled()
    with ledger():
        job = lq.claim_next_job()
        assert job is not None and job["id"] == queued
    page.goto(SLOP_CHECK, wait_until="load", timeout=120_000)
    assert "Checking the newest draft." in page.locator(".ws-card .ws-notice.tone-info").inner_text()
    assert VERDICT in page.locator(".ws-verdict-box").inner_text()   # the last result stays shown (PW22)
    with ledger():
        assert lq.finish_job(queued, "failed", "There is no draft to check yet.")
    page.goto(SLOP_CHECK, wait_until="load", timeout=120_000)
    assert "The last Check again did not run: There is no draft to check yet." in page.locator(".ws-card").inner_text()
    act(page, page.locator(".ws-card").get_by_role("button", name="Check again"))
    assert "Check again is queued. The worker scans the newest draft when no step is waiting." in notice(page)
    with ledger():
        job = lq.claim_next_job()
    assert job is not None and job["kind"] == "slop_scan" and job["pursuit_id"] == site["rev-check"]
    assert job["requested_by"] == "Shaun Jones"


# ------------------------------------------------------------------------------ Final checks, Submit and results (phase 9b)

def test_final_checks_show_seven_checks_and_wait_for_a_ready_final_version(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-fin-gate", "final")
    card = page.locator(".ws-card")
    assert "final checks, 4 of 7 passed" in card.inner_text().lower()
    checks = card.locator(".ws-checks li").all_inner_texts()
    assert len(checks) == 7 and "Placeholder sweep" in checks[2] and "1 left" in checks[2] and "not ready" in checks[3]
    still = card.locator("[aria-label='Final checks'] .ws-spots li").first
    assert "White paper. [NEEDS INPUT: hours per task]" in still.inner_text() and "for David Wood" in still.inner_text()
    assert still.locator("a").get_attribute("href") == "?step=final&view=slop&lines=3"
    approve = card.get_by_role("button", name="Approve and continue")
    assert approve.is_disabled()
    assert "The AI slop check says Not ready: 1 NEEDS INPUT" in card.locator(".ws-call").inner_text()
    assert card.get_by_role("button", name="Check again").count() == 1
    # The owner fills it in and Check again saves a Ready scan of the final version: the checks update and Approve opens.
    with ledger():
        _scan_final(site["fin-gate"], ready=True)
    open_workspace(page, "ws-fin-gate", "final")
    card = page.locator(".ws-card")
    checks = card.locator(".ws-checks li").all_inner_texts()
    assert "none left, checked again" in checks[2] and "Ready: band clean (provisional), checked again" in checks[3]
    act(page, card.get_by_role("button", name="Approve and continue"))
    assert "Approved. Submit is queued for the worker." in notice(page)
    assert steps_of(site["fin-gate"])[-2:] == [("final", 1, "approved"), ("submit", 1, "queued")]


def test_the_submit_gate_lists_the_files_the_portal_and_what_was_checked(page: Any, site: dict[str, int]) -> None:
    open_workspace(page, "ws-sub-gate", "submit")
    card = page.locator(".ws-card")
    assert "GATE · SUBMIT" in card.locator(".ws-band").inner_text().upper()
    rows = card.locator(".ws-rows").first.inner_text()
    assert "White paper (PDF): email attachment" in rows and "SAM.gov, before 2027-01-15, time not given" in rows
    assert card.get_by_role("link", name="Open the call page").get_attribute("href") == "https://example.invalid/ws-sub-gate"
    assert "1 item is still open" in card.inner_text() and "Email the PDF to the contracting officer" in card.inner_text()
    assert card.get_by_role("button", name="Mark submitted").count() == 0   # nobody is logged in


def test_mark_submitted_records_the_submission_and_the_calls_decision(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-sub-gate", "submit")
    card = page.locator(".ws-card")
    assert card.locator("input[name=result_by]").input_value() == "2027-04-15"
    card.locator("input[name=confirmation]").fill("DSIP-123")
    card.locator("input[name=submitted_at]").fill("2026-10-27T15:40")
    act(page, card.get_by_role("button", name="Mark submitted"))
    assert "Marked submitted." in notice(page)
    pursuit = pursuit_of(site["sub-gate"])
    assert (pursuit["state"], pursuit["confirmation_number"], pursuit["result_expected_by"], pursuit["submitted_by"]) == (
        "submitted", "DSIP-123", "2027-04-15", "David Wood")
    assert pursuit["submitted_at"] == "2026-10-27T21:40:00Z"   # 15:40 in Denver, still on summer time
    assert pursuit["result_expected_source"].startswith("About 90 days after the deadline")
    assert steps_of(site["sub-gate"])[-1] == ("submit", 1, "approved")
    with ledger():
        assert lq.get_call("ws-sub-gate")["human_status"] == "submitted"
    assert "Submitted" in page.locator(".ws-crumb").inner_text()


def test_mark_submitted_on_a_page_left_open_while_the_call_changed_saves_nothing(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-sub-stale", "submit")
    with ledger():
        lq.set_human("ws-sub-stale", "not_relevant", "Shaun Jones")
    act(page, page.locator(".ws-card").get_by_role("button", name="Mark submitted"))
    assert ("The call's decision changed since the page loaded: it is not relevant, by Shaun Jones now. Nothing saved"
            in page.locator(".notice").first.inner_text())
    assert pursuit_of(site["sub-stale"])["state"] == "working"
    assert steps_of(site["sub-stale"])[-1] == ("submit", 1, "ready")


def test_submitted_and_waiting_puts_overdue_first_and_no_news_yet_moves_the_date(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    page.goto(f"{WEB}/proposals/submitted", wait_until="load", timeout=120_000)
    first = page.locator("tbody tr").first
    assert "Waiting late" in first.inner_text() and "result overdue" in first.inner_text()
    first.locator("summary", has_text="No news yet").click()
    act(page, first.get_by_role("button", name="Push the date"))
    assert "No news yet: the result is now expected by 2026-10-30." in notice(page)
    pursuit = pursuit_of(site["sw-late"])
    assert pursuit["result_expected_by"] == "2026-10-30" and pursuit["result_expected_source"].startswith("No news yet on ")


def test_record_result_moves_the_call_to_results_with_its_notes(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    page.goto(f"{WEB}/proposals/submitted", wait_until="load", timeout=120_000)
    row = page.locator("tbody tr", has_text="Waiting for a result")
    row.locator("summary", has_text="Record result").click()
    row.get_by_label("Lost").check()
    row.locator("textarea[name=debrief]").fill("Weak teaming")
    row.locator("textarea[name=next_time]").fill("Name the research partner before the outline.")
    act(page, row.get_by_role("button", name="Record result"))
    assert "Recorded: lost. The call is in Results. Ask for a debrief" in notice(page)
    pursuit = pursuit_of(site["sw-result"])
    assert (pursuit["result"], pursuit["result_by"], pursuit["debrief"], pursuit["next_time"]) == (
        "lost", "David Wood", "Weak teaming", "Name the research partner before the outline.")
    page.goto(f"{WEB}/proposals/results", wait_until="load", timeout=120_000)
    result = page.locator("tbody tr", has_text="Waiting for a result").inner_text()
    assert "lost" in result and "Debrief: Weak teaming" in result and "Next time: Name the research partner" in result


def test_a_call_submitted_outside_the_workspace_gets_its_result_kept_too(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    page.goto(f"{WEB}/proposals/submitted", wait_until="load", timeout=120_000)
    row = page.locator("tbody tr", has_text="Submitted outside the workspace")
    row.locator("summary", has_text="Record result").click()
    row.get_by_label("Cancelled by the agency").check()
    act(page, row.get_by_role("button", name="Record result"))
    assert "Recorded: cancelled by the agency." in notice(page)
    with ledger():
        pursuit = next(p for p in (lq.get_pursuit(i) for i in range(1, 200)) if p and p["call_id"] == "ws-sw-outside")
    assert (pursuit["state"], pursuit["owner"], pursuit["submitted_by"], pursuit["result"]) == (
        "submitted", "Shaun Jones", "Shaun Jones", "cancelled_by_agency")


# ------------------------------------------------------------------------------ Builds on from the Proposal Library (phase 6b)

def test_start_the_draft_builds_on_past_work_from_the_library(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    page.goto(f"{WEB}/proposals", wait_until="load", timeout=120_000)
    page.locator('[data-start-draft="ws-start"]').first.click()
    dialog = page.locator("dialog[open]")
    assert "past submissions" in dialog.inner_text().lower() and "company reference" in dialog.inner_text().lower()
    dialog.get_by_label("Vigilant eagle 27, Vulcan SOF, 2026-03-17").check()
    act(page, dialog.get_by_role("button", name="Start the draft"))
    assert "Started the draft" in notice(page)
    with ledger():
        started = next(p for p in (lq.get_pursuit(i) for i in range(1, 300)) if p and p["call_id"] == "ws-start")
    assert json.loads(started["builds_on"]) == [{"id": "lib-ve27", "name": "2026-03-17_vulcan-sof_vigilant-eagle-27"}]


def test_the_outline_adds_past_work_from_the_library_and_refreshes_the_list(page: Any, site: dict[str, int]) -> None:
    log_in(page, "David Wood")
    open_workspace(page, "ws-outline-lib", "outline")
    card = page.locator(".ws-card")
    card.locator("select[name=add_id]").select_option("lib-bio")
    act(page, card.locator("form", has=page.locator("select[name=add_id]")).get_by_role("button", name="Add"))
    assert "Added past work: David Wood bio.docx" in notice(page)
    with ledger():
        assert json.loads(lq.get_pursuit(site["outline-lib"])["builds_on"]) == [{"id": "lib-bio", "name": "David Wood bio.docx"}]
    open_workspace(page, "ws-outline-lib", "outline")
    options = page.locator(".ws-card select[name=add_id] option").all_inner_texts()
    assert not any("David Wood bio" in o for o in options)   # chosen already, so no longer offered
    assert "2026-10-29" in page.locator(".ws-card").inner_text()   # when the worker last indexed the library
    act(page, page.locator(".ws-card").get_by_role("button", name="Refresh the list"))
    assert "The worker refreshes the Proposal Library's list when no step is waiting." in notice(page)
    open_workspace(page, "ws-outline-lib", "outline")
    act(page, page.locator(".ws-card").get_by_role("button", name="Refresh the list"))
    assert "already waiting for the worker" in page.locator(".notice").first.inner_text()
