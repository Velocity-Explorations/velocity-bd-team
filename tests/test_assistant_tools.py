"""The assistant's read tools, against a made-up portal and a throwaway ledger."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from assistant import tools
from ledger import queries as lq
from ledger.db import q, tx
from portals.registry import Portal

UTC = timezone.utc
NOW = datetime.now(UTC).replace(microsecond=0)


def due(days: float) -> str:
    """A deadline the way Vulcan writes one, `days` from now."""
    return (NOW + timedelta(days=days)).strftime("%d %b %Y : %H:%M UTC").upper()


@pytest.fixture
def portal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Portal:
    keywords = tmp_path / "keywords.yaml"
    keywords.write_text(
        "broad_keywords:\n  - software\n  - data\n\ntight_keywords:\n  - machine learning\n\n"
        "blocklist_patterns:\n  - '\\bspare parts\\b'\n",
        encoding="utf-8",
    )
    notes = tmp_path / "NOTES.md"
    notes.write_text("# Example portal\n\nCodes arrive by email.\n", encoding="utf-8")
    fake = Portal(slug="example", name="Example", fetch=lambda *a, **k: {}, filter=lambda rows: ([], []),
                  keywords=keywords, how_to_submit="Email the program office.", notes=notes)
    monkeypatch.setattr(tools.registry, "discover", lambda: [fake])
    return fake


def add_call(call_id: str, title: str, run: int, *, description: str = "", due_date: str | None = None,
             extra: dict | None = None) -> None:
    lq.upsert_call({"id": call_id, "portal": "Example", "title": title, "description": description,
                    "due_date": due_date, "url": f"https://example.invalid/{call_id}", "extra": extra or {}}, run)


def finish(run_id: int, status: str, counts: dict, error: str | None = None, started: datetime | None = None) -> None:
    lq.finish_run(run_id, status, counts, error=error)
    if started:
        with tx() as c:
            q(c, "UPDATE runs SET started_at = ?, finished_at = ? WHERE id = ?",
              (started.strftime("%Y-%m-%dT%H:%M:%SZ"), (started + timedelta(minutes=3)).strftime("%Y-%m-%dT%H:%M:%SZ"), run_id))


# --------------------------------------------------------------------------- portals

def test_resolve_portal_by_slug_or_name(portal: Portal) -> None:
    assert tools.resolve_portal("example") is portal
    assert tools.resolve_portal("EXAMPLE") is portal and tools.resolve_portal("Example") is portal
    with pytest.raises(tools.ToolError) as exc:
        tools.resolve_portal("nope")
    assert "example" in str(exc.value)


def test_portal_profile(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example", component="example")
    add_call("ex-1", "Software", run)
    lq.set_filter("ex-1", "kept", tier="broad", keywords=["software"])
    lq.set_review("ex-1", "yes", "fits")
    finish(run, "completed", {"fetched": 1})
    p = tools.portal_profile("example")
    assert p["name"] == "Example" and p["how_to_submit"] == "Email the program office."
    assert "Codes arrive by email." in p["notes"]
    assert p["keywords"]["broad"] == ["software", "data"] and p["keywords"]["tight"] == ["machine learning"]
    assert p["calls"]["total"] == 1 and p["calls"]["by_verdict"]["yes"] == 1
    assert p["last_run"]["status"] == "completed" and "Example" in p["text"]


# ------------------------------------------------------------------- explain a verdict

def test_explain_rejections(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-block", "Spare parts kit", run)
    lq.set_filter("ex-block", "rejected", reason="blocklist: \\bspare parts\\b")
    add_call("ex-none", "Lawn care", run)
    lq.set_filter("ex-none", "rejected", reason="no keyword match")
    block = tools.explain_call("ex-block")["text"]
    assert "blocklist pattern \\bspare parts\\b" in block and "never reached the AI review" in block
    assert "none of Example's keywords" in tools.explain_call("ex-none")["text"]


def test_explain_a_reviewed_and_decided_call(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-ml", "Machine learning software", run, extra={"vulcan_closed": True})
    lq.set_filter("ex-ml", "kept", tier="tight", keywords=["software", "machine learning"])
    lq.set_review("ex-ml", "maybe", "Software fits, but the scope is unclear.")
    lq.set_human("ex-ml", "not_relevant", "David Wood", "2026-10-17T10:00:00Z")
    lq.append_note("ex-ml", "hardware heavy", by="David Wood", at="2026-10-17T10:01:00Z")
    e = tools.explain_call("ex-ml")
    assert e["filter"] == {"result": "kept", "reason": None, "tier": "tight", "keywords": ["software", "machine learning"]}
    assert e["review"]["verdict"] == "maybe"
    text = e["text"]
    assert "tight match on software, machine learning" in text
    assert "The AI review said maybe: Software fits, but the scope is unclear." in text
    assert "marked it Not relevant" in text and "hardware heavy" in text and "closed" in text


def test_explain_pending_and_unknown(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-new", "New call", run)
    assert "not been filtered yet" in tools.explain_call("ex-new")["text"]
    with pytest.raises(tools.ToolError):
        tools.explain_call("missing")


# ------------------------------------------------------------------------ brief a call

def test_brief_a_call(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-brief", "Edge AI", run, description="Detect drones at the edge with computer vision.",
             due_date=due(10.5), extra={
                 "vulcan_objectives": ["OTA Prototype", "Market Research"],
                 "vulcan_files_required": ["White Paper Template (See template)", "Quad Chart Template (See template)"],
                 "vulcan_documents": ["Submitter's Guide"],
                 "vulcan_tags": ["Counter-UAS"],
                 "vulcan_instructions": "Create a Scout Card and upload a white paper.",
             })
    b = tools.brief_call("ex-brief", now=NOW)
    assert b["days_left"] == 10 and b["closed"] is False
    assert b["objectives"] == ["OTA Prototype", "Market Research"]
    assert b["files_required"][1] == "Quad Chart Template (See template)"
    assert b["how_to_submit"] == "Create a Scout Card and upload a white paper."
    for words in ("Edge AI", "10 days left", "OTA Prototype, Market Research", "Quad Chart Template",
                  "Detect drones", "https://example.invalid/ex-brief"):
        assert words in b["text"], words


def test_brief_falls_back_to_the_portals_how_to_submit(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-plain", "Plain call", run, due_date=due(-2), extra={"vulcan_closed": True})
    b = tools.brief_call("ex-plain", now=NOW)
    assert b["how_to_submit"] == "Email the program office."
    assert b["closed"] is True and b["days_left"] == -3 and "closed" in b["text"]


# --------------------------------------------------------------------- deadline reminders

def test_upcoming_deadlines_lists_pursued_calls_due_soon(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    plan = {
        "ex-soon": (3.5, "pursue"), "ex-later": (12.5, "pursue"), "ex-too-far": (20, "pursue"),
        "ex-past": (-1, "pursue"), "ex-sent": (4, "submitted"), "ex-open": (5, None),
    }
    for call_id, (days, status) in plan.items():
        add_call(call_id, call_id.replace("ex-", "").title(), run, due_date=due(days))
        if status:
            lq.set_human(call_id, status, "David Wood")
    found = tools.upcoming_deadlines(days=14, now=NOW)
    assert [c["id"] for c in found["calls"]] == ["ex-soon", "ex-later"]
    assert found["calls"][0]["days_left"] == 3
    assert "3 days" in found["text"] and "Soon" in found["text"]
    assert tools.upcoming_deadlines(days=2, now=NOW)["calls"] == []
    assert "Nothing marked Pursue" in tools.upcoming_deadlines(days=2, now=NOW)["text"]


# ---------------------------------------------------------------------- watch the scraper

def test_scraper_health_reports_failures_and_badly_read_pages(ledger_db: str, portal: Portal) -> None:
    assert "has never run" in tools.scraper_health("example", now=NOW)["text"]

    good = lq.start_run("Example", component="example")
    add_call("ex-good", "Good page", good, description="Software", due_date=due(9))
    add_call("ex-bad", "Bad page", good, description="", due_date=None, extra={"vulcan_description_fallback": True})
    finish(good, "completed", {"fetched": 2}, started=NOW - timedelta(days=2))
    first = tools.scraper_health("example", now=NOW)["portals"][0]
    assert first["latest"]["status"] == "completed" and first["consecutive_failures"] == 0
    assert first["badly_read"]["count"] == 1 and first["badly_read"]["examples"] == ["Bad page"]
    assert "1 of 2 pages read badly" in first["text"]

    for _ in range(2):
        bad = lq.start_run("Example", component="example")
        finish(bad, "error", {"fetched": 0}, error="LoginFailed: Vulcan SOF login returned False")
    second = tools.scraper_health("example", now=NOW)["portals"][0]
    assert second["consecutive_failures"] == 2
    assert "failed" in second["text"] and "LoginFailed" in second["text"] and "2 runs in a row" in second["text"]


def test_scraper_health_flags_a_scan_overdue(ledger_db: str, portal: Portal) -> None:
    old = lq.start_run("Example", component="example")
    finish(old, "completed", {"fetched": 0}, started=NOW - timedelta(days=10))
    assert "no completed scan for 10 days" in tools.scraper_health("example", now=NOW)["text"]


# ------------------------------------------------------------------------- weekly summary

def test_weekly_summary(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-yes", "Yes call", run, due_date=due(6))
    lq.set_filter("ex-yes", "kept", tier="broad", keywords=["software"])
    lq.set_review("ex-yes", "yes", "fits")
    add_call("ex-no", "No call", run)
    lq.set_filter("ex-no", "kept", tier="broad", keywords=["data"])
    lq.set_review("ex-no", "no", "hardware")
    add_call("ex-rej", "Rejected call", run)
    lq.set_filter("ex-rej", "rejected", reason="no keyword match")
    add_call("ex-picked", "Picked call", run, due_date=due(30))
    lq.set_review("ex-picked", "maybe", "unclear")
    lq.set_human("ex-picked", "pursue", "David Wood")
    s = tools.weekly_summary("example", days=7, now=NOW)
    assert s["new"]["total"] == 4 and s["new"]["by_verdict"] == {"yes": 1, "maybe": 1, "no": 1, "rejected by filter": 1}
    assert [c["id"] for c in s["closing_soon"]] == ["ex-yes"]
    assert [d["id"] for d in s["decided"]] == ["ex-picked"]
    for words in ("Example", "4 new calls", "Yes call", "Closing within 14 days", "Pursue: Picked call"):
        assert words in s["text"], words


# ----------------------------------------------------------------- settings change preview

def test_preview_shows_what_a_keyword_change_would_keep_and_drop(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    add_call("ex-twin", "Digital twin for ships", run)
    add_call("ex-sw", "Software for spare parts", run)
    add_call("ex-data", "Data platform", run)
    lq.set_human("ex-data", "pursue", "David Wood")
    p = tools.preview_keyword_change("example", add_broad=["Digital Twin"], add_block=[r"\bplatform\b"])
    assert p["changes"]["add_broad"] == ["digital twin"]
    assert [c["id"] for c in p["newly_kept"]] == ["ex-twin"]
    assert [c["id"] for c in p["newly_dropped"]] == ["ex-data"]
    assert any("Pursue" in w and "Data platform" in w for w in p["warnings"])
    assert "would keep 1" in p["text"] and "drop 1" in p["text"]


def test_preview_rejects_bad_input(ledger_db: str, portal: Portal) -> None:
    with pytest.raises(tools.ToolError):
        tools.preview_keyword_change("example", add_block=["(unclosed"])
    with pytest.raises(tools.ToolError):
        tools.preview_keyword_change("example")
    with pytest.raises(tools.ToolError):
        tools.preview_keyword_change("example", remove_broad=["not there"])


# ------------------------------------------------------------------------- tuning report

def test_tuning_report_needs_enough_decisions(ledger_db: str, portal: Portal) -> None:
    assert "Only 0 decisions" in tools.tuning_report("example", min_examples=3)["text"]


def test_tuning_report_finds_patterns(ledger_db: str, portal: Portal) -> None:
    run = lq.start_run("Example")
    for n in range(3):
        add_call(f"ex-hw{n}", f"Turret hardware build {n}", run)
        lq.set_filter(f"ex-hw{n}", "kept", tier="broad", keywords=["data"])
        lq.set_review(f"ex-hw{n}", "maybe", "might fit")
        lq.set_human(f"ex-hw{n}", "not_relevant", "David Wood")
    for n in range(3):
        add_call(f"ex-sw{n}", f"Analytics software {n}", run)
        lq.set_filter(f"ex-sw{n}", "kept", tier="broad", keywords=["software"])
        lq.set_review(f"ex-sw{n}", "yes", "fits")
        lq.set_human(f"ex-sw{n}", "pursue", "David Wood")
    r = tools.tuning_report("example", min_examples=3)
    kinds = {(s["kind"], s["value"]) for s in r["suggestions"]}
    assert ("add_block", r"\bturret\b") in kinds and ("add_block", r"\bhardware\b") in kinds
    assert ("remove_broad", "data") in kinds
    assert len(r["ai_disagreements"]) == 3
    assert "Turret hardware build 0" in r["text"]


# -------------------------------------------------------------------------- the registry

def test_every_tool_is_described_for_a_model() -> None:
    names = [t.name for t in tools.TOOLS]
    assert len(names) == len(set(names))
    for t in tools.TOOLS:
        assert t.permission in ("read", "propose") and t.description and callable(t.run)
        assert t.parameters["type"] == "object" and "properties" in t.parameters
    assert {"explain_call", "brief_call", "upcoming_deadlines", "scraper_health", "weekly_summary",
            "portal_profile", "preview_keyword_change", "tuning_report"} <= set(names)
