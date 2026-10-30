"""The Writer's worker (PRO-577): its own lock, the heartbeat, claiming and running steps, what they cost
against the pursuit's cap, key gates approval, Ask for changes, cancel, and steps a stopped worker left.
The model is a stand-in; nothing here reaches Anthropic."""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Callable

import pytest

import run
from drafting import llm, worker
from ledger import queries as lq

FENCE = "`" * 3
REPLIES = {
    "discovery": f'# Discovery summary\nFound the notice.\n{FENCE}json\n{{"key_points": ["Found the notice"], "tasks": {{}}}}\n{FENCE}',
    "opportunity summary": f'# Opportunity summary\nArmy edge AI.\n{FENCE}json\n{{"key_points": ["Army"], "worth_it": "yes"}}\n{FENCE}',
    "alignment": f'# Alignment\nStrong.\n{FENCE}json\n{{"key_points": ["Strong"], "verdict": "Strong fit"}}\n{FENCE}',
    "analyzing requirements": "# Requirements analysis\nKEYWORDS: edge AI",
    "submission checklist": json.dumps({"key_points": ["PDF"], "checklist": [], "submit_by": "2026-11-30",
                                        "format": {"font": "Arial", "size": 11}}),
    "go or no-go brief": f'# Go or no-go brief\nGo.\n{FENCE}json\n{{"key_points": ["Go"], "fit": "Strong fit", "recommendation": "go"}}\n{FENCE}',
    "building outline": f'# Outline\n## 1. Technical Approach\n{FENCE}json\n{{"key_points": ["One section"], "sections": []}}\n{FENCE}',
    "drafting response": "# White paper\n\nEcho C2 runs offline " + chr(0x2014) + " on laptops. [NEEDS INPUT: rates]",
    "compliance check": "## 1. Keywords\n- ok\n---CORRECTED DRAFT---\n# White paper v2",
    "building checklist": "# Checklist\n- [ ] rates",
    "formatting document": "# White paper, final\n\nBody.",
    "final compliance re-check": "## 1. Keywords\n- ok",
    "submission packet": f'# Submission packet\nEmail it.\n{FENCE}json\n{{"key_points": ["Email"], "files": [{{"file": "PDF", "slot": "email"}}]}}\n{FENCE}',
}


class Model:
    """Stands in for llm.generate: a canned reply per call label, each call reporting the tokens it is told."""

    def __init__(self, tokens: dict[str, tuple[int, int]] | None = None, fail: set[str] | None = None,
                 on_call: Callable[[str], None] | None = None) -> None:
        self.tokens = tokens or {}
        self.fail = fail or set()
        self.on_call = on_call
        self.calls: list[dict[str, Any]] = []

    def __call__(self, prompt: str, system: str = "", model: str | None = None, max_tokens: int = 8000,
                 timeout: float = 600, phase_label: str = "", *, abort: llm.AbortToken | None = None,
                 on_usage: Callable[[llm.Usage], None] | None = None, **_: Any) -> str:
        if abort is not None and abort.is_set():
            raise llm.DraftCancelled(f"{phase_label}: cancelled")
        self.calls.append({"label": phase_label, "prompt": prompt, "system": system, "model": model})
        if self.on_call:
            self.on_call(phase_label)
        if phase_label in self.fail:
            raise llm.PhaseError(f"{phase_label}: the model refused this request")
        tokens_in, tokens_out = self.tokens.get(phase_label, (1_000, 500))
        if on_usage:
            on_usage(llm.Usage(phase_label=phase_label, model=model or llm.DEFAULT_MODEL, input_tokens=tokens_in,
                               output_tokens=tokens_out, cache_read_tokens=0, cache_write_tokens=0, seconds=1.0,
                               truncated=False, request_id=""))
        if phase_label.startswith("review "):
            change = {"section": "Title", "now": "# White paper v2", "suggested": "# White paper v2, reviewed", "why": "Clearer"}
            return f"# Review\n{FENCE}json\n{json.dumps({'key_points': ['One change'], 'changes': [change] if phase_label.startswith('review 1 ') else []})}\n{FENCE}"
        if phase_label.startswith("facts used: "):
            return f'{FENCE}json\n{{"used": [{{"id": "F-02", "claims": ["the UEI"]}}], "unsupported": []}}\n{FENCE}'
        return REPLIES[phase_label]

    def labels(self) -> list[str]:
        return [c["label"] for c in self.calls]


@pytest.fixture
def local(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """The worker's files, lock and logs under tmp_path."""
    monkeypatch.setattr(worker, "DATA_DIR", tmp_path / "drafting")
    monkeypatch.setattr(worker, "LOCK_FILE", tmp_path / "drafting" / "worker.lock")
    monkeypatch.setattr(worker, "WORK_ROOT", tmp_path / "drafting" / "pursuits")
    return tmp_path


def _pursuit(call_id: str = "sam-1", **options: Any) -> int:
    run_id = lq.start_run("sam_gov")
    lq.upsert_call({"id": call_id, "portal": "SAM.gov", "title": f"Edge AI {call_id}", "type": "Sources Sought",
                    "department": "DEPT OF THE ARMY", "due_date": "2026-12-01", "description": "The Army seeks edge AI."}, run_id)
    lq.set_human(call_id, "pursue", "David Wood")
    return lq.start_pursuit(call_id, "David Wood", format="White paper", **options)


def _steps(pursuit_id: int) -> list[tuple[str, int, str]]:
    return [(s["step"], s["attempt"], s["state"]) for s in lq.pursuit_steps(pursuit_id)]


def _scans(pursuit_id: int) -> list[dict[str, Any]]:
    from ledger.db import q, rows, tx

    with tx() as conn:
        return rows(q(conn, "SELECT * FROM slop_scans WHERE pursuit_id = ? ORDER BY id", (pursuit_id,)))


def _drain(model: Model) -> int:
    ran = 0
    while worker.work_once(generate=model):
        ran += 1
    return ran


# ------------------------------------------------------------------------------ the lock

def test_the_worker_has_its_own_lock_apart_from_the_pipeline() -> None:
    assert worker.LOCK_FILE.name == "worker.lock" and worker.LOCK_FILE.parent.name == "drafting"
    assert worker.LOCK_FILE != run.LOCK_FILE


def test_one_worker_at_a_time_and_a_dead_ones_lock_is_taken_over(local: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    lock = worker.LOCK_FILE
    run.acquire_lock(local / "pipeline.lock")             # Sunday's scan holds its own lock...
    worker.take_lock()                                    # ...and the worker still starts
    assert lock.read_text(encoding="utf-8").split()[0] == str(os.getpid())
    with pytest.raises(worker.WorkerRunning, match="Another worker is running"):
        worker.take_lock()
    worker.release_lock()
    assert not lock.exists()
    lock.parent.mkdir(parents=True, exist_ok=True)
    lock.write_text("4242 2026-10-01T00:00:00+00:00\n", encoding="utf-8")
    monkeypatch.setattr(worker, "_pid_alive", lambda pid: False)
    worker.take_lock()
    assert lock.read_text(encoding="utf-8").split()[0] == str(os.getpid())
    worker.release_lock()
    run.release_lock(local / "pipeline.lock")


# ------------------------------------------------------------------------------ the loop

def test_nothing_queued_means_nothing_to_do(ledger_db: str, local: Path) -> None:
    model = Model()
    assert worker.work_once(generate=model) is False and model.calls == []


def test_the_worker_drafts_with_the_model_WRITER_MODEL_names(ledger_db: str, local: Path,
                                                             monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WRITER_MODEL", "grok-4.7")
    _pursuit()
    model = Model()
    assert worker.work_once(generate=model) is True
    assert model.calls[0]["model"] == "grok-4.7"


def test_a_step_is_saved_ready_with_what_it_cost_and_waits_for_the_owner(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit()
    model = Model()
    assert worker.work_once(generate=model) is True
    assert model.labels() == ["discovery"] and model.calls[0]["model"] == llm.DEFAULT_MODEL
    [step] = lq.pursuit_steps(pursuit_id)
    assert (step["state"], step["summary"]) == ("ready", "- Found the notice")
    assert json.loads(step["files"]) == [{"name": "Discovery summary", "local": f"pursuit-{pursuit_id}/discovery.md",
                                          "word": f"pursuit-{pursuit_id}/discovery.docx"}]
    assert (local / "drafting" / "pursuits" / f"pursuit-{pursuit_id}" / "discovery.md").exists()
    assert json.loads(step["content"])["document"].startswith("# Discovery summary")
    assert json.loads(step["task_states"])["summary"] == "done"
    assert step["cost_usd"] == pytest.approx(0.007)          # 1,000 tokens in and 500 out on Sonnet 5.5
    assert lq.get_pursuit(pursuit_id)["cost_usd"] == pytest.approx(0.007)
    assert [e["kind"] for e in lq.pursuit_events(pursuit_id)] == ["started", "step_saved"]
    assert lq.get_worker(lq.WORKER)["state"] == "idle"
    assert worker.work_once(generate=model) is False         # every step approved: it waits for David


def test_with_key_gates_only_the_worker_approves_and_runs_on_to_the_gate(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit(approval_mode="key_gates")
    model = Model()
    assert _drain(model) == 5
    assert _steps(pursuit_id) == [("discovery", 1, "approved"), ("summary", 1, "approved"), ("alignment", 1, "approved"),
                                  ("requirements", 1, "approved"), ("go_no_go", 1, "ready")]
    assert {s["decided_by"] for s in lq.pursuit_steps(pursuit_id)[:4]} == {lq.AUTO_APPROVER}
    assert [e["kind"] for e in lq.pursuit_events(pursuit_id)].count("auto_approved") == 4
    assert model.labels() == ["discovery", "opportunity summary", "alignment", "analyzing requirements",
                              "submission checklist", "go or no-go brief"]


def test_ask_for_changes_reruns_the_step_with_the_note_and_the_last_version(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit()
    model = Model()
    worker.work_once(generate=model)
    first = lq.pursuit_steps(pursuit_id)[0]
    assert lq.ask_changes(first["id"], "David Wood", "Check the DSIP topic page too")
    worker.work_once(generate=model)
    assert _steps(pursuit_id) == [("discovery", 1, "changes_asked"), ("discovery", 2, "ready")]
    prompt = model.calls[-1]["prompt"]
    assert "Check the DSIP topic page too" in prompt and "Found the notice." in prompt


def test_a_step_that_would_start_over_the_cap_waits_for_the_owner(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit(budget_usd=0.0)
    model = Model()
    assert worker.work_once(generate=model) is True
    [step] = lq.pursuit_steps(pursuit_id)
    assert (step["state"], step["error"], step["cost_usd"]) == ("blocked", "budget reached", 0)
    assert model.calls == []
    assert [e["kind"] for e in lq.pursuit_events(pursuit_id)][-1] == "blocked"


def test_spending_that_crosses_the_cap_stops_the_step_there(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit(approval_mode="key_gates", budget_usd=1.0)
    model = Model(tokens={"analyzing requirements": (1_000_000, 0)})       # $2 on Sonnet 5.5
    _drain(model)
    requirements = lq.pursuit_steps(pursuit_id)[-1]
    assert (requirements["step"], requirements["state"], requirements["error"]) == ("requirements", "blocked", "budget reached")
    assert requirements["cost_usd"] == pytest.approx(2.0)
    assert lq.get_pursuit(pursuit_id)["cost_usd"] == pytest.approx(2.0 + 3 * 0.007)
    assert "submission checklist" not in model.labels()                   # the second call never went out
    assert worker.work_once(generate=model) is False


def test_closing_the_pursuit_stops_its_step_and_keeps_the_cost(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit()
    model = Model(on_call=lambda label: lq.close_pursuit(pursuit_id, "David Wood", "Partner pulled out"))
    worker.work_once(generate=model)
    [step] = lq.pursuit_steps(pursuit_id)
    assert (step["state"], step["cost_usd"]) == ("stopped", pytest.approx(0.007))
    assert [e["kind"] for e in lq.pursuit_events(pursuit_id)][-2:] == ["closed", "stopped"]


def test_a_pursuit_closed_between_two_calls_makes_no_more(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit(approval_mode="key_gates")
    model = Model(on_call=lambda label: label == "analyzing requirements" and lq.close_pursuit(pursuit_id, "David Wood"))
    _drain(model)
    assert lq.pursuit_steps(pursuit_id)[-1]["state"] == "stopped"
    assert model.labels()[-1] == "analyzing requirements"


def test_a_failed_step_says_why(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit()
    worker.work_once(generate=Model(fail={"discovery"}))
    [step] = lq.pursuit_steps(pursuit_id)
    assert (step["state"], step["error"]) == ("failed", "discovery: the model refused this request")
    assert lq.retry_step(step["id"], "David Wood")                        # and Retry queues it again


def test_a_step_the_worker_cannot_run_yet_fails_with_the_reason(ledger_db: str, local: Path,
                                                                monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(worker, "RUNNERS", {step: run for step, run in worker.RUNNERS.items() if step != "outline"})
    pursuit_id = _pursuit(approval_mode="key_gates")
    model = Model()
    _drain(model)
    gate = lq.pursuit_steps(pursuit_id)[-1]
    lq.approve_step(gate["id"], "David Wood", decision="go")
    worker.work_once(generate=model)
    outline = lq.pursuit_steps(pursuit_id)[-1]
    assert (outline["step"], outline["state"], outline["error"]) == ("outline", "failed", "The worker cannot run Outline yet.")


def test_every_step_has_its_work() -> None:
    assert set(worker.RUNNERS) == set(lq.STEPS)


def test_with_key_gates_a_pursuit_runs_from_discovery_to_the_submit_gate(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit(approval_mode="key_gates")
    model = Model()
    _drain(model)
    lq.approve_step(lq.pursuit_steps(pursuit_id)[-1]["id"], "David Wood", decision="go")   # the owner's gate
    _drain(model)
    outline = lq.pursuit_steps(pursuit_id)[-1]
    assert (outline["step"], outline["state"]) == ("outline", "ready")                     # a key gate waits
    lq.approve_step(outline["id"], "David Wood")
    _drain(model)
    assert [(step, state) for step, _, state in _steps(pursuit_id)][5:] == [
        ("outline", "approved"), ("draft", "approved"), ("compliance", "approved"), ("reviews", "approved"),
        ("final", "approved"), ("submit", "ready")]
    work = local / "drafting" / "pursuits" / f"pursuit-{pursuit_id}"
    saved = {path.name for path in work.iterdir()}
    assert {"outline.md", "draft_v1.md", "draft_v2.md", "draft_v3.md", "draft_final.md", "submission_packet.md"} <= saved
    for path in work.glob("*.md"):
        assert chr(0x2013) not in path.read_text(encoding="utf-8") and chr(0x2014) not in path.read_text(encoding="utf-8")
    draft = next(s for s in lq.pursuit_steps(pursuit_id) if s["step"] == "draft")
    assert chr(0x2014) not in draft["content"] and "Echo C2 runs offline, on laptops" in json.loads(draft["content"])["document"]
    reviews = next(s for s in lq.pursuit_steps(pursuit_id) if s["step"] == "reviews")
    changes = lq.step_changes(reviews["id"])
    assert len(changes) == 1 and {(c["state"], c["decided_by"]) for c in changes} == {("accepted", lq.AUTO_APPROVER)}
    assert "# White paper v2, reviewed" in (work / "draft_v3.md").read_text(encoding="utf-8")
    assert [s["draft_name"] for s in _scans(pursuit_id)] == ["draft_v1.md", "draft_v2.md", "draft_final.md"]
    submit = json.loads(lq.pursuit_steps(pursuit_id)[-1]["content"])
    assert [c["check"] for c in submit["checks"]] == ["Checklist", "Placeholders", "AI slop check", "Dashes",
                                                      "Internal submit-by date"]
    assert submit["files"] == [{"file": "PDF", "slot": "email"}]
    from docx import Document
    first_draft = Document(str(work / "draft_v1.docx"))      # the solicitation's format, from Requirements and checklist
    assert (first_draft.styles["Normal"].font.name, first_draft.styles["Normal"].font.size.pt) == ("Arial", 11.0)
    assert {"draft_final.docx", "checklist.docx", "slop_report.docx", "submission_packet.docx"} <= saved


# ---------------------------------------------------------------------------- serving

def test_serving_once_beats_recovers_left_steps_and_stops_cleanly(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit()
    left = lq.claim_next_step()                       # a worker stopped while it worked on Discovery
    assert worker.serve(once=True, generate=Model()) == 0
    step = lq.get_step(left["id"])
    assert (step["state"], step["error"]) == ("failed", worker.LEFT_WORKING)
    beat = lq.get_worker(lq.WORKER)
    assert (beat["state"], beat["doing"]) == ("stopped", None)
    assert not worker.LOCK_FILE.exists()
    assert _steps(pursuit_id) == [("discovery", 1, "failed")]


def test_a_second_worker_leaves_quietly(ledger_db: str, local: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    worker.LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    worker.LOCK_FILE.write_text("4242 2026-10-28T00:00:00+00:00\n", encoding="utf-8")
    monkeypatch.setattr(worker, "_pid_alive", lambda pid: True)
    assert worker.serve(once=True, generate=Model()) == 0
    assert lq.get_worker(lq.WORKER) is None
    assert worker.LOCK_FILE.read_text(encoding="utf-8").startswith("4242")


def test_check_again_scans_the_newest_draft_when_no_step_is_waiting(ledger_db: str, local: Path) -> None:
    pursuit_id = _pursuit()
    worker.work_once(generate=Model())                       # Discovery is ready; nothing is queued now
    work = local / "drafting" / "pursuits" / f"pursuit-{pursuit_id}"
    (work / "draft_v1.md").write_text("# White paper\n\n[NEEDS INPUT: rates] " + "Words. " * 200, encoding="utf-8")
    job_id = lq.queue_job("slop_scan", pursuit_id, None, "David Wood")
    assert worker.work_once(generate=Model()) is True
    job = lq.get_job(job_id)
    assert (job["state"], job["result"]) == ("done", "Not ready: 1 NEEDS INPUT; band clean (provisional)")
    scan = lq.latest_slop_scan(pursuit_id)
    assert (scan["draft_name"], scan["step_id"]) == ("draft_v1.md", None)
    other = lq.queue_job("slop_scan", _pursuit("sam-2"), None, "David Wood")    # a pursuit with no draft yet
    while worker.work_once(generate=Model()):
        pass
    assert (lq.get_job(other)["state"], lq.get_job(other)["result"]) == ("failed", "There is no draft to check yet.")
