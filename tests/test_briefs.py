"""The Monday brief, kept per week for the dashboard (migration 005), with a Top 10 across portals (PRO-492)."""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

import run as pipeline
from assistant import tools
from ledger import queries as lq
from portals import registry
from tests.test_assistant_tools import due
from tests.test_pipeline import fake_portal, isolated, slack_posts   # noqa: F401  (fixtures)


def this_monday() -> str:
    today = datetime.now(timezone.utc).date()
    return (today - timedelta(days=today.weekday())).isoformat()


def seed(call_id: str, portal: str, verdict: str, days: float | None, extra: dict | None = None) -> None:
    run = lq.start_run(portal)
    lq.upsert_call({"id": call_id, "portal": portal, "title": call_id, "due_date": due(days) if days is not None else None,
                    "url": f"https://example.invalid/{call_id}", "extra": extra or {}}, run)
    lq.set_filter(call_id, "kept", tier="broad", keywords=["software"])
    lq.set_review(call_id, verdict, f"{call_id} fits. More words.")


def test_a_brief_replaces_the_same_week_and_portal_and_keeps_other_weeks(ledger_db: str) -> None:
    lq.save_brief("2026-10-19", "Vulcan SOF", {"waiting": 1}, "pipeline")
    lq.save_brief("2026-10-19", "Vulcan SOF", {"waiting": 2}, "pipeline")
    lq.save_brief("2026-10-19", None, {"top": []}, "pipeline")
    lq.save_brief("2026-10-12", "Vulcan SOF", {"waiting": 5}, "pipeline")
    week = lq.briefs_for_week("2026-10-19")
    assert {b["portal"]: json.loads(b["body"]) for b in week} == {"Vulcan SOF": {"waiting": 2}, None: {"top": []}}
    assert len(week) == 2 and all(b["written_by"] == "pipeline" for b in week)
    assert lq.brief_weeks() == ["2026-10-19", "2026-10-12"]


def test_top_calls_ranks_open_undecided_calls_across_portals(ledger_db: str) -> None:
    seed("v-maybe-soon", "Vulcan SOF", "maybe", 2.5)
    seed("f-yes-later", "SSC Front Door", "yes", 20.5)
    seed("v-yes-soon", "Vulcan SOF", "yes", 5.5)
    seed("f-yes-undated", "SSC Front Door", "yes", None)
    seed("v-no", "Vulcan SOF", "no", 3.5)                                   # rated no: never a pick
    seed("f-past", "SSC Front Door", "yes", -1)                             # its deadline has passed
    seed("v-decided", "Vulcan SOF", "yes", 4.5)
    lq.set_human("v-decided", "pursue", "David Wood")                      # already decided
    seed("f-closed", "SSC Front Door", "yes", 6.5, extra={"sscfd_closed": True})
    top = tools.top_calls(limit=10)
    assert [c["id"] for c in top] == ["v-yes-soon", "f-yes-later", "f-yes-undated", "v-maybe-soon"]
    first = top[0]
    assert (first["portal"], first["verdict"], first["days_left"], first["reason"]) == ("Vulcan SOF", "yes", 5, "v-yes-soon fits.")
    assert [c["id"] for c in tools.top_calls(limit=2)] == ["v-yes-soon", "f-yes-later"]


def test_write_brief_stores_each_portal_and_the_top_ten_without_posting(isolated, slack_posts,
                                                                         monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "acquire_lock", lambda *a, **k: pytest.fail("a brief never takes the pipeline lock"))
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    seed("fake-1", "Fake", "yes", 6.5)
    assert pipeline.main(["--write-brief"]) == 0
    assert slack_posts == []
    week = lq.briefs_for_week(this_monday())
    bodies = {b["portal"]: json.loads(b["body"]) for b in week}
    assert set(bodies) == {"Fake", None}
    assert bodies["Fake"]["waiting"] == 1 and [c["id"] for c in bodies["Fake"]["top_picks"]] == ["fake-1"]
    assert "Fake" in bodies["Fake"]["health"]
    assert [c["id"] for c in bodies[None]["top"]] == ["fake-1"] and "judges" in bodies[None]
