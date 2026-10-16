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
        from portals.vulcan_sof.filter import filter_calls
        return filter_calls(rows_)

    return Portal(slug="fake", name="Fake", fetch=fetch, filter=filt, fetch_timeout=timeout, needs_browser=False)


def _counts() -> tuple[int, int]:
    with tx() as c:
        return rows(q(c, "SELECT COUNT(*) AS n FROM calls"))[0]["n"], rows(q(c, "SELECT COUNT(*) AS n FROM runs"))[0]["n"]


@pytest.fixture
def isolated(ledger_db: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(pipeline, "LOCK_FILE", tmp_path / "pipeline.lock")
    monkeypatch.setattr(pipeline, "LOG_DIR", tmp_path / "logs")
    monkeypatch.setattr(pipeline, "alert", lambda text: alerts.append(text))
    alerts: list[str] = []
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

    assert pipeline.main(["--no-review"]) == 0
    out = capsys.readouterr().out
    assert "0 new call(s)" in out and "(nothing new)" in out
    run2 = lq.get_run(2)
    assert run2 and '"new": 0' in run2["stage_counts"]


def test_dry_run_leaves_ledger_unchanged(isolated, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    before = _counts()
    assert pipeline.main(["--dry-run", "--no-review"]) == 0
    out = capsys.readouterr().out
    assert "DRY RUN: nothing was committed" in out and "DIGEST: Fake: 1 new call(s)" in out
    assert _counts() == before


def test_fetch_timeout_is_skipped_not_fatal(isolated, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal("hang")])
    monkeypatch.setattr(pipeline, "FORCE_CLOSE_GRACE_S", 0)
    killed: list[bool] = []
    monkeypatch.setattr("portals.vulcan_sof.browser.force_close", lambda kill_orphans=True: killed.append(True))
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
    assert "vulcan_sof" in slugs
    vulcan = registry.get("vulcan_sof")
    assert vulcan.name == "Vulcan SOF" and vulcan.fetch_timeout == 300 and vulcan.needs_browser
