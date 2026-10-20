"""run.py end to end on SQLite with a fake, browser-free portal."""
from __future__ import annotations

import subprocess
import threading
import time
from pathlib import Path

import pytest

import run as pipeline
from ledger import queries as lq
from ledger.db import tx, q, rows
from portals import registry
from portals.registry import Portal
from tests.test_assistant_tools import due
from tests.test_reviewer import FakeModel


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



# ------------------------------------------------------------------ scheduled Slack posts

@pytest.fixture
def slack_posts(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    import slack.sink as sink
    sent: list[str] = []

    def fake_post(text: str, client=None, blocks: list[dict] | None = None) -> str:
        parts = [text]
        for block in blocks or []:
            parts += [block["text"]["text"]] if "text" in block else []
            parts += [element.get("text", "") for element in block.get("elements", [])]
        sent.append("\n".join(parts))
        return "1.0"

    monkeypatch.setattr(sink, "post_text", fake_post)
    return sent


def test_remind_posts_only_when_something_is_due(isolated, slack_posts, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(pipeline, "acquire_lock", lambda *a, **k: pytest.fail("a reminder never takes the pipeline lock"))
    assert pipeline.main(["--remind"]) == 0
    assert slack_posts == [] and "nothing to post" in capsys.readouterr().out
    seed = lq.start_run("Fake")
    lq.upsert_call({"id": "soon", "portal": "Fake", "title": "Soon", "due_date": due(3.5)}, seed)
    lq.set_human("soon", "pursue", "David Wood")
    assert pipeline.main(["--remind"]) == 0
    assert len(slack_posts) == 1 and slack_posts[0].startswith("*Deadline reminder*") and "Soon" in slack_posts[0]


def test_post_summary_covers_each_portal_and_the_scraper(isolated, slack_posts, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "acquire_lock", lambda *a, **k: pytest.fail("a summary never takes the pipeline lock"))
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    seed = lq.start_run("Fake", component="fake")
    lq.upsert_call({"id": "fake-1", "portal": "Fake", "title": "Analytics software"}, seed)
    lq.finish_run(seed, "completed", {"fetched": 1})
    assert pipeline.main(["--post-summary"]) == 0
    assert len(slack_posts) == 1 and slack_posts[0].startswith("Weekly BD summary, week of")
    assert "*Fake*: 1 new this week" in slack_posts[0] and "Scraper: Fake" in slack_posts[0]


# ------------------------------------------------------------------------ waiting for the lock

def test_wait_for_lock_starts_once_the_other_run_finishes(isolated) -> None:
    pipeline.acquire_lock()
    threading.Timer(0.3, pipeline.release_lock).start()
    pipeline.acquire_lock(wait_s=5, poll_s=0.05)
    pipeline.release_lock()


def test_wait_for_lock_gives_up_in_time(isolated) -> None:
    pipeline.acquire_lock()
    try:
        started = time.time()
        with pytest.raises(pipeline.LockHeld):
            pipeline.acquire_lock(wait_s=0.3, poll_s=0.05)
        assert time.time() - started < 3
    finally:
        pipeline.release_lock()


def test_wait_lock_flag_is_in_minutes() -> None:
    assert pipeline.parse_args(["--wait-lock", "30"]).wait_lock == 30
    assert pipeline.parse_args([]).wait_lock == 0


# ------------------------------------------------------------------- approved change requests

SETTINGS = r"""# Test settings.

broad_keywords:
  - software

tight_keywords:
  - machine learning

blocklist_patterns:
  - '\bspare parts\b'
"""


def _git(cwd: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()


@pytest.fixture
def settings_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "settings"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    for key, value in (("user.name", "Test Person"), ("user.email", "test@example.invalid"),
                       ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
        _git(repo, "config", key, value)
    (repo / "keywords.yaml").write_bytes(SETTINGS.encode("utf-8"))
    _git(repo, "add", "keywords.yaml")
    _git(repo, "commit", "-q", "-m", "start")
    return repo


def settings_portal(path: Path) -> Portal:
    def filt(rows_):
        from portals.shared.keyword_filter import filter_calls
        return filter_calls(rows_, path)
    return Portal(slug="fake", name="Fake", fetch=lambda *a, **k: {}, filter=filt, keywords=path, needs_browser=False)


def approved(kind: str, summary: str, **fields) -> int:
    rid = lq.create_request(kind, summary, "Dana", **fields)
    assert lq.decide_request(rid, True, "David Wood")
    return rid


def test_apply_with_nothing_approved_does_nothing(isolated, monkeypatch: pytest.MonkeyPatch, capsys) -> None:
    monkeypatch.setattr(pipeline, "acquire_lock", lambda *a, **k: pytest.fail("took the lock with nothing to do"))
    lq.create_request("scan", "Scan Fake now", "Dana", portal="fake")       # proposed, not approved
    assert pipeline.main(["--apply-requests"]) == 0
    assert "No approved requests to carry out." in capsys.readouterr().out
    assert not pipeline.LOG_DIR.exists()


def test_apply_keyword_change_commits_refilters_and_reviews(isolated, settings_repo: Path, slack_posts,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    path = settings_repo / "keywords.yaml"
    portal = settings_portal(path)
    monkeypatch.setattr(registry, "discover", lambda: [portal])
    seed = lq.start_run("Fake")
    lq.upsert_call({"id": "twin", "portal": "Fake", "title": "Digital twin for ships", "description": ""}, seed)
    lq.upsert_call({"id": "sw", "portal": "Fake", "title": "Software tools", "description": ""}, seed)
    portal.filter(lq.calls_where(portal="Fake"))
    assert lq.get_call("twin")["filter_result"] == "rejected"
    lq.set_review("sw", "yes", "Software.")              # already kept and reviewed; only the twin is new
    rid = approved("keyword_change", "Fake keywords: add broad keyword 'digital twin'", portal="fake",
                   payload={"changes": {"add_broad": ["digital twin"]}})
    model = FakeModel(["VERDICT: yes\nREASON: Digital twin software."])
    monkeypatch.setattr(pipeline, "review_model", lambda: model)

    assert pipeline.main(["--apply-requests"]) == 0
    req = lq.get_request(rid)
    assert req["status"] == "applied", req["result"]
    assert req["result"].startswith("Committed ") and "1 newly kept, 0 newly dropped" in req["result"]
    text = path.read_text(encoding="utf-8")
    assert f"  # added {pipeline.today()} by request #{rid}, approved by David Wood\n  - digital twin\n" in text
    assert _git(settings_repo, "log", "-1", "--format=%s") == (
        f"chore(fake): add broad keyword 'digital twin' (request #{rid}, approved by David Wood)")
    assert _git(settings_repo, "status", "--porcelain") == ""
    twin = lq.get_call("twin")
    assert twin["filter_result"] == "kept" and twin["ai_verdict"] == "yes"
    assert len(slack_posts) == 1 and f"#{rid}" in slack_posts[0] and "Committed" in slack_posts[0]


def test_apply_keyword_change_waits_for_a_clean_main(isolated, settings_repo: Path, slack_posts,
                                                     monkeypatch: pytest.MonkeyPatch) -> None:
    path = settings_repo / "keywords.yaml"
    monkeypatch.setattr(registry, "discover", lambda: [settings_portal(path)])
    rid = approved("keyword_change", "Fake keywords: add broad keyword 'digital twin'", portal="fake",
                   payload={"changes": {"add_broad": ["digital twin"]}})
    _git(settings_repo, "checkout", "-q", "-b", "dev")
    assert pipeline.main(["--apply-requests"]) == 0
    req = lq.get_request(rid)
    assert req["status"] == "approved" and req["result"].startswith("Waiting:") and "branch dev" in req["result"]
    assert path.read_bytes().decode("utf-8") == SETTINGS and slack_posts == []
    assert not pipeline.LOG_DIR.exists()

    _git(settings_repo, "checkout", "-q", "main")
    path.write_bytes((SETTINGS + "# a local edit\n").encode("utf-8"))
    assert pipeline.main(["--apply-requests"]) == 0
    req = lq.get_request(rid)
    assert req["status"] == "approved" and "uncommitted" in req["result"]


def test_apply_scan_runs_the_portal_now(isolated, slack_posts, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    monkeypatch.setattr(pipeline, "review_model", lambda: FakeModel(["VERDICT: yes\nREASON: fits"]))
    rid = approved("scan", "Scan Fake now", portal="fake", payload={})
    assert pipeline.main(["--apply-requests"]) == 0
    req = lq.get_request(rid)
    run_id = lq.latest_run_id(component="fake")
    assert req["status"] == "applied" and req["result"].startswith(f"Run #{run_id} completed")
    assert lq.get_run(run_id)["status"] == "completed" and lq.get_call("fake-0")["ai_verdict"] == "yes"
    assert pipeline._test_capture["posted"] == ["fake-0"]   # type: ignore[attr-defined]


def test_apply_rereview_asks_again_with_the_teams_context(isolated, slack_posts, monkeypatch: pytest.MonkeyPatch) -> None:
    seed = lq.start_run("Fake")
    lq.upsert_call({"id": "c2", "portal": "Fake", "title": "C2 data layer", "description": "radios"}, seed)
    lq.set_filter("c2", "kept", tier="broad", keywords=["data"])
    lq.set_review("c2", "no", "Hardware.")
    model = FakeModel(["VERDICT: yes\nREASON: Software over radios."])
    monkeypatch.setattr(pipeline, "review_model", lambda: model)
    rid = approved("rereview", "Re-review 'C2 data layer' with the team's context", call_id="c2",
                   payload={"context": "It is a software layer."})
    assert pipeline.main(["--apply-requests"]) == 0
    req = lq.get_request(rid)
    assert req["status"] == "applied" and req["result"] == "The AI review changed from no to yes: Software over radios."
    assert "Context from the team: It is a software layer." in model.prompts[0]


def test_apply_fault_report_waits_for_github_then_files(isolated, slack_posts, monkeypatch: pytest.MonkeyPatch) -> None:
    rid = approved("fault_report", "Report a scraper fault in Fake", portal="fake",
                   payload={"title": "Scraper fault: Fake: logins fail", "body": "Logins fail."})
    monkeypatch.setattr(pipeline, "github_waiting", lambda: "Waiting: this repo has no GitHub remote yet.")
    assert pipeline.main(["--apply-requests"]) == 0
    req = lq.get_request(rid)
    assert req["status"] == "approved" and "no GitHub remote" in req["result"]

    filed: list[tuple[str, str]] = []
    monkeypatch.setattr(pipeline, "github_waiting", lambda: None)
    monkeypatch.setattr(pipeline, "file_issue",
                        lambda title, body: filed.append((title, body)) or "https://github.com/o/r/issues/1")
    assert pipeline.main(["--apply-requests"]) == 0
    req = lq.get_request(rid)
    assert req["status"] == "applied" and req["result"] == "Filed https://github.com/o/r/issues/1"
    assert filed[0][0] == "Scraper fault: Fake: logins fail"
    assert filed[0][1].startswith("Logins fail.") and f"Approved by David Wood (request #{rid})" in filed[0][1]


def test_apply_leaves_drafts_for_the_writer(isolated, slack_posts, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "acquire_lock", lambda *a, **k: pytest.fail("drafts are not run.py's to carry out"))
    rid = approved("draft", "Start a response draft for 'Open call'", call_id="x", payload={"notes": ""})
    assert pipeline.main(["--apply-requests"]) == 0
    assert lq.get_request(rid)["status"] == "approved" and slack_posts == []


def test_apply_records_a_failure(isolated, slack_posts) -> None:
    rid = approved("rereview", "Re-review a missing call", call_id="missing", payload={"context": "x"})
    assert pipeline.main(["--apply-requests"]) == 1
    req = lq.get_request(rid)
    assert req["status"] == "failed" and "No call with id 'missing'" in req["result"]
    assert len(slack_posts) == 1 and "failed" in slack_posts[0]


def test_apply_waits_while_a_pipeline_runs(isolated, slack_posts, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(registry, "discover", lambda: [fake_portal()])
    rid = approved("scan", "Scan Fake now", portal="fake", payload={})
    pipeline.acquire_lock()
    try:
        assert pipeline.main(["--apply-requests"]) == 3
    finally:
        pipeline.release_lock()
    assert lq.get_request(rid)["status"] == "approved"


def test_apply_marks_an_interrupted_request_failed(isolated, slack_posts) -> None:
    rid = approved("scan", "Scan Fake now", portal="fake", payload={})
    assert lq.claim_request(rid)
    assert pipeline.main(["--apply-requests"]) == 1
    req = lq.get_request(rid)
    assert req["status"] == "failed" and req["result"].startswith("Interrupted")


def fake_gh(monkeypatch: pytest.MonkeyPatch, token: str | None, returncode: int = 0,
            stderr: str = "") -> list[dict[str, str] | None]:
    """Stub gh and the token setting; return the env each gh call received."""
    envs: list[dict[str, str] | None] = []

    def run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        envs.append(kwargs.get("env"))  # type: ignore[arg-type]
        return subprocess.CompletedProcess(cmd, returncode, stdout="https://github.com/o/r/issues/7\n", stderr=stderr)

    monkeypatch.setattr(pipeline.subprocess, "run", run)
    monkeypatch.setattr(pipeline.config, "get", lambda key, default=None: token if key == "BD_GITHUB_TOKEN" else default)
    return envs


def test_file_issue_uses_the_pipeline_github_token(monkeypatch: pytest.MonkeyPatch) -> None:
    envs = fake_gh(monkeypatch, "fake-pipeline-token")
    assert pipeline.file_issue("Scraper fault", "Logins fail.") == "https://github.com/o/r/issues/7"
    assert envs[0] is not None and envs[0]["GH_TOKEN"] == "fake-pipeline-token"


def test_file_issue_without_a_pipeline_token_uses_the_gh_login(monkeypatch: pytest.MonkeyPatch) -> None:
    envs = fake_gh(monkeypatch, None)
    pipeline.file_issue("Scraper fault", "Logins fail.")
    assert envs == [None]


@pytest.mark.parametrize("stderr, hint", [("HTTP 401: Bad credentials", "expired"),
                                          ("HTTP 403: Resource not accessible by personal access token", "repo scope")])
def test_refused_pipeline_token_names_the_key_and_the_fix(monkeypatch: pytest.MonkeyPatch, stderr: str, hint: str) -> None:
    fake_gh(monkeypatch, "fake-pipeline-token", returncode=1, stderr=stderr)
    with pytest.raises(RuntimeError, match="BD_GITHUB_TOKEN") as raised:
        pipeline.file_issue("Scraper fault", "Logins fail.")
    assert hint in str(raised.value) and "fake-pipeline-token" not in str(raised.value)
