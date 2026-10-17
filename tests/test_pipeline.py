"""run.py end to end on SQLite with a fake, browser-free portal."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

import run as pipeline
from ledger import queries as lq
from ledger.db import tx, q, rows
from portals import registry
from portals.registry import Portal


def fake_portal(behaviour: str = "ok", timeout: int = 300) -> Portal:
    def fetch(page, run_id, limit=None):
        if behaviour == "hang":
            # Sleep, then return WITHOUT writing: the thread outlives the test and its
            # fixtures, so any write here would land in whatever DATABASE_URL is live.
            time.sleep(3)
            return {"found": 0, "scraped": 0, "new": 0, "failed": 0}
        if behaviour == "boom":
            raise RuntimeError("portal exploded")
        titles = ["Edge AI thing", "Hose assembly supply"][:limit]
        new = sum(lq.upsert_call({"id": f"fake-{n}", "portal": "Fake", "title": t, "description": "software"}, run_id)
                  for n, t in enumerate(titles))
        return {"found": len(titles), "scraped": len(titles), "new": new, "failed": 0}

    def filt(rows_):
        from portals.shared.keyword_filter import filter_calls
        from portals.vulcan_sof.portal import KEYWORDS_PATH
        return filter_calls(rows_, KEYWORDS_PATH)

    return Portal(slug="fake", name="Fake", fetch=fetch, filter=filt, fetch_timeout=timeout, needs_browser=False)


def _counts() -> tuple[int, int]:
    with tx() as c:
        return rows(q(c, "SELECT COUNT(*) AS n FROM calls"))[0]["n"], rows(q(c, "SELECT COUNT(*) AS n FROM runs"))[0]["n"]


@pytest.fixture
def isolated(ledger_db: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pipeline, "LOCK_FILE", tmp_path / "pipeline.lock")
    monkeypatch.setattr(pipeline, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(pipeline, "alert", lambda text: alerts.append(text))
    import slack.sink as sink
    monkeypatch.setattr(sink, "collect_feedback", lambda *a, **k: [])
    monkeypatch.setattr(sink, "post_call", lambda row, client=None: posted.append(row["id"]) or "1.0")
    monkeypatch.setattr(sink, "post_run_summary", lambda summary, client=None: summaries.append(summary) or "1.1")
    alerts: list[str] = []
    posted: list[str] = []
    summaries: list[dict] = []
    pipeline._test_capture = {"alerts": alerts, "posted": posted, "summaries": summaries}   # type: ignore[attr-defined]
    return alerts


def test_full_run_then_rerun(isolated, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    assert pipeline.main(["--no-review"]) == 0
    out = capsys.readouterr().out
    assert "DIGEST: Fake: 1 new call(s)" in out and "[MAYBE] Edge AI thing" in out
    run1 = lq.get_run(1)
    assert run1 and run1["status"] == "completed" and run1["log_path"].endswith(".log")
    assert '"fetched": 2' in run1["stage_counts"] and '"new": 1' in run1["stage_counts"]
    hose = lq.get_call("fake-1")
    assert hose and hose["filter_result"] == "rejected"
    edge = lq.get_call("fake-0")
    assert edge and edge["ai_verdict"] == "maybe" and edge["ai_reasoning"] == pipeline.NO_REVIEW_REASON

    assert pipeline._test_capture["posted"] == ["fake-0"]   # type: ignore[attr-defined]
    assert pipeline._test_capture["summaries"][0]["new"] == 1   # type: ignore[attr-defined]

    assert pipeline.main(["--no-review"]) == 0
    out = capsys.readouterr().out
    assert "0 new call(s)" in out and "(nothing new)" in out
    run2 = lq.get_run(2)
    assert run2 and '"new": 0' in run2["stage_counts"]
    assert pipeline._test_capture["posted"] == ["fake-0"] and pipeline._test_capture["summaries"][1]["new"] == 0   # type: ignore[attr-defined]


def test_dry_run_leaves_ledger_unchanged(isolated, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    before = _counts()
    assert pipeline.main(["--dry-run", "--no-review"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN: nothing was committed" in out and "DIGEST: Fake: 1 new call(s)" in out
    assert "would post 1 card(s)" in out and "[MAYBE] Edge AI thing" in out
    assert pipeline._test_capture["posted"] == [] and pipeline._test_capture["summaries"] == []   # type: ignore[attr-defined]
    assert _counts() == before


def test_fetch_timeout_is_skipped_not_fatal(isolated, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal("hang")])
    monkeypatch.setattr(pipeline, "FORCE_CLOSE_GRACE_S", 0)
    killed: list[bool] = []
    monkeypatch.setattr("portals.shared.browser.force_close", lambda kill_orphans=True: killed.append(True))
    code = pipeline.main(["--fetch-timeout", "1", "--no-review"])
    assert code == 1
    run = lq.get_run(1)
    assert run and run["status"] == "skipped_timeout" and "exceeded 1s" in run["error"]
    assert killed == [True]
    assert any("FETCH TIMEOUT" in a or "skipped_timeout" in a for a in isolated)


def test_fetch_error_is_recorded_and_alerted(isolated, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal("boom")])
    assert pipeline.main(["--no-review"]) == 1
    run = lq.get_run(1)
    assert run and run["status"] == "error" and "RuntimeError: portal exploded" in run["error"]
    assert isolated and "portal exploded" in isolated[0]


def test_skip_fetch_reviews_pending_rows(isolated, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    seed = lq.start_run("Fake")
    lq.upsert_call({"id": "fake-9", "portal": "Fake", "title": "Machine learning tool", "description": ""}, seed)
    assert pipeline.main(["--skip-fetch", "--no-review"]) == 0
    row = lq.get_call("fake-9")
    assert row and row["filter_result"] == "kept" and row["ai_verdict"] == "maybe"


def test_lock_blocks_second_pipeline(isolated, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    pipeline.acquire_lock()
    try:
        assert pipeline.main(["--no-review"]) == 3
        assert "Another pipeline is running" in capsys.readouterr().out
    finally:
        pipeline.release_lock()
    assert not pipeline.LOCK_FILE.exists()


def test_unknown_portal_slug(isolated, capsys) -> None:
    assert pipeline.main(["--portal", "nope"]) == 2
    assert "no portal with slug 'nope'" in capsys.readouterr().out


def test_digest_order() -> None:
    rows_ = [
        {"ai_verdict": "maybe", "title": "B", "due_date": "01 JAN 2027", "url": "u", "ai_reasoning": "r"},
        {"ai_verdict": "yes", "title": "C", "due_date": "05 FEB 2027", "url": "u", "ai_reasoning": "r"},
        {"ai_verdict": "yes", "title": "A", "due_date": "01 FEB 2027", "url": "u", "ai_reasoning": "r"},
    ]
    titles = [line.split("] ")[1].split("\n")[0] for line in pipeline.digest_lines(rows_)]
    assert titles == ["A", "C", "B"]


def test_registry_discovers_vulcan_sof() -> None:
    slugs = [p.slug for p in registry.discover()]
    assert "vulcan_sof" in slugs and "shared" not in slugs
    vulcan = registry.get("vulcan_sof")
    assert vulcan.name == "Vulcan SOF" and vulcan.fetch_timeout == 300 and vulcan.needs_browser
    assert vulcan.keywords and vulcan.keywords.name == "keywords.yaml" and vulcan.keywords.exists()
    assert vulcan.notes and vulcan.notes.exists() and "Scout Card" in vulcan.how_to_submit


def test_feedback_only_runs_collect_and_exits(isolated, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    import slack.sink as sink
    monkeypatch.setattr(sink, "collect_feedback", lambda *a, **k: [{"id": "x", "title": "T", "notes": ["n"], "card_updated": True}])
    assert pipeline.main(["--feedback-only"]) == 0
    out = capsys.readouterr().out
    assert "feedback-only: 1 change(s) recorded" in out and "notes=1 card_updated=yes" in out
    assert lq.latest_run_id() is None   # no runs row for a feedback pass


def test_deliver_run_reposts_only_undelivered(isolated, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    import slack.sink as sink
    monkeypatch.setattr(sink, "post_call", lambda row, client=None: None)   # Slack down
    assert pipeline.main(["--no-review"]) == 0
    assert lq.get_call("fake-0")["slack_ts"] is None   # type: ignore[index]
    monkeypatch.setattr(sink, "post_call", lambda row, client=None: pipeline._test_capture["posted"].append(row["id"]) or "9.9")   # type: ignore[attr-defined]
    assert pipeline.main(["--deliver-run", "1"]) == 0
    assert "deliver-run 1: 1 of 1 card(s) posted" in capsys.readouterr().out
    assert pipeline._test_capture["posted"] == ["fake-0"]   # type: ignore[attr-defined]
    assert pipeline.main(["--deliver-run", "99"]) == 2


def test_watch_alerts_when_a_scan_reads_pages_badly(isolated, monkeypatch: pytest.MonkeyPatch) -> None:
    def fetch(page, run_id, limit=None):
        for n in range(4):
            lq.upsert_call({"id": f"bad-{n}", "portal": "Fake", "title": f"Page {n}", "description": "software"}, run_id)
        return {"found": 4, "scraped": 4, "new": 4, "failed": 0}

    flaky = Portal(slug="fake", name="Fake", fetch=fetch, filter=lambda rows: ([], []), needs_browser=False)
    monkeypatch.setattr(registry, "discover", lambda: [flaky])
    assert pipeline.main(["--no-review"]) == 0
    assert any("read 4 of 4 pages badly" in a and "Page 0" in a for a in isolated)
