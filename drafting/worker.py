"""The Writer's worker (Writer Plan W2a; redesign phase 5, PRO-577): one always-on process on David's PC
that runs the proposal workspace's steps, one at a time.

    python -m drafting.worker             # until stopped: claim a queued step, else wait 20 seconds
    python -m drafting.worker --once      # run at most one step, then exit (to try it by hand)

It holds data/drafting/worker.lock while it runs, never data/pipeline.lock, so it never holds up
Sunday's scan, and a second worker finds the lock and leaves. It beats in the `workers` table on
every poll, and every 30 seconds while a step runs: that beat is how the dashboard knows drafting is
set up (P8). At start it fails any step a stopped worker left working, so the owner can Retry it
(PW15).

Each step runs only while its pursuit is under its spending cap; otherwise it waits as "budget
reached" (PW19). The step's work (drafting/qualify.py, drafting/write.py) asks the model through a
meter that adds each call's cost (drafting/costs.py) to the step and stops the step once spending
crosses the cap. Before each call, and every 30 seconds during one, the worker checks that the
pursuit is still being worked and stops the step when the owner closed it. The work is saved ready,
or failed with the reason; with key gates only, the worker approves it (accepting the reviewers'
changes at Reviews) and queues the next step (PW5). With no step waiting it runs the oldest job,
such as Check again on the AI slop check (PW22). Files stay under data/drafting/pursuits/pursuit-<id>/
until Drive (phase 6), and the card's text, like every file, has its dashes replaced. The worker logs
ids, states and costs, never a call's text or title.
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import subprocess
import sys
import threading
from collections.abc import Callable, Mapping
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from drafting import costs, inputs, llm, qualify, scan, slop_gate, word, write
from drafting.pipeline import PHASE_TIMEOUT_S
from drafting.prompts import Prompt
from drafting.steps import StepContext, StepResult, fix_dashes, latest_draft
from ledger import queries as lq
from ledger.db import release as release_connection

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data" / "drafting"
LOCK_FILE = DATA_DIR / "worker.lock"
WORK_ROOT = DATA_DIR / "pursuits"
POLL_S = 20
WATCH_S = 30
BUDGET_REACHED = "budget reached"
LEFT_WORKING = "The worker stopped while it worked on this step. Retry runs it again."
RUNNERS: dict[str, Callable[[StepContext], StepResult]] = {**qualify.RUNNERS, **write.RUNNERS}

log = logging.getLogger("drafting.worker")


# ------------------------------------------------------------------------------ the lock

class WorkerRunning(RuntimeError):
    pass


def _pid_alive(pid: int) -> bool:
    """Whether a Python process with this id is running. On Windows a reused id belongs to some other
    program, so only a python or pythonw process counts."""
    if sys.platform == "win32":
        # os.kill(pid, 0) would TERMINATE the process on Windows; ask tasklist instead.
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH", "/FO", "CSV"], capture_output=True,
                                 text=True, timeout=15)
        except Exception:   # noqa: BLE001 (cannot tell: assume it runs, so two workers never start)
            return True
        return any(line.lower().startswith('"python') and f'"{pid}"' in line for line in out.stdout.splitlines())
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def _holder(path: Path) -> int | None:
    """The process id in a lock file: None without one, -1 when it cannot be read."""
    try:
        return int(path.read_text(encoding="utf-8").split()[0])
    except FileNotFoundError:
        return None
    except (OSError, ValueError, IndexError):
        return -1


def take_lock() -> None:
    """Take the worker's lock, or raise WorkerRunning while another worker holds it. A lock whose worker is
    gone is taken over."""
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    holder = _holder(LOCK_FILE)
    if holder is not None:
        if holder > 0 and _pid_alive(holder):
            raise WorkerRunning(f"Another worker is running (pid {holder}, lock {LOCK_FILE}). Not starting.")
        log.warning("Taking over the lock of worker pid %s, which is not running", holder)
        LOCK_FILE.unlink(missing_ok=True)
    try:
        with LOCK_FILE.open("x", encoding="utf-8") as f:
            f.write(f"{os.getpid()} {datetime.now(timezone.utc).isoformat()}\n")
    except FileExistsError as exc:
        raise WorkerRunning(f"Another worker took the lock {LOCK_FILE} just now. Not starting.") from exc


def release_lock() -> None:
    """Remove the lock if this process holds it."""
    if _holder(LOCK_FILE) == os.getpid():
        LOCK_FILE.unlink(missing_ok=True)


# ----------------------------------------------------------------------- one step

class Meter:
    """What a step has spent, against what its pursuit may still spend. Crossing the cap stops every call
    after the one that crossed it."""

    def __init__(self, spent: float, budget: float, abort: llm.AbortToken) -> None:
        self.spent, self.budget, self.abort = spent, budget, abort
        self.cost = 0.0
        self.over = False

    def record(self, usage: llm.Usage) -> None:
        self.cost += costs.cost_of(usage)
        if self.spent + self.cost >= self.budget:
            self.over = True
            self.abort.set()


def _stopped(pursuit_id: int) -> bool:
    return (lq.get_pursuit(pursuit_id) or {}).get("state") != "working"


class Watcher(threading.Thread):
    """While a step runs: the heartbeat every WATCH_S, and the stop when its pursuit is closed."""

    def __init__(self, pursuit_id: int, doing: str, abort: llm.AbortToken) -> None:
        super().__init__(daemon=True, name="worker-watch")
        self.pursuit_id, self.doing, self.abort = pursuit_id, doing, abort
        self.done = threading.Event()

    def run(self) -> None:
        try:
            while not self.done.wait(WATCH_S):
                try:
                    lq.worker_beat(lq.WORKER, "working", self.doing)
                    if _stopped(self.pursuit_id):
                        log.info("Pursuit %s was closed; stopping its step", self.pursuit_id)
                        self.abort.set()
                except Exception as exc:   # noqa: BLE001 (the ledger may be unreachable for a moment)
                    log.warning("Heartbeat failed: %s", type(exc).__name__)
        finally:
            release_connection()

    def stop(self) -> None:
        self.done.set()
        self.join(timeout=10)


def _previous(step: Mapping[str, Any]) -> dict[str, Any] | None:
    """The attempt before this one at the same step, whose work Ask for changes is about."""
    if int(step["attempt"]) <= 1:
        return None
    return next((s for s in lq.pursuit_steps(step["pursuit_id"])
                 if s["step"] == step["step"] and int(s["attempt"]) == int(step["attempt"]) - 1), None)


def _undashed(value: Any) -> Any:
    """A step's card text and content with the en and em dashes replaced, as its files are."""
    if isinstance(value, str):
        return fix_dashes(value)
    if isinstance(value, list):
        return [_undashed(v) for v in value]
    if isinstance(value, dict):
        return {key: _undashed(v) for key, v in value.items()}
    return value


def _word_format(pursuit_id: int) -> word.Format:
    """The format the solicitation sets, as Requirements and checklist found it; plain defaults before then."""
    found = lq.latest_steps(pursuit_id).get("requirements")
    try:
        content = json.loads(found["content"]) if found and found.get("content") else {}
    except ValueError:
        content = {}
    return word.format_from(content.get("format") if isinstance(content, dict) else None)


def _why(exc: Exception) -> str:
    """Why a step failed, in words for the step's card (PW15)."""
    text = str(exc) if isinstance(exc, llm.PhaseError) else f"{type(exc).__name__}: {exc}"
    return text[:300]


def _run(step: dict[str, Any], pursuit: dict[str, Any], label: str, doing: str, generate: Callable[..., str],
         model: str, today: date) -> None:
    runner = RUNNERS.get(step["step"])
    if runner is None:
        lq.fail_step(step["id"], f"The worker cannot run {label} yet.")
        log.warning("Step %s: no work for %s yet", step["id"], step["step"])
        return
    if float(pursuit["cost_usd"]) >= float(pursuit["budget_usd"]):
        lq.block_step(step["id"], BUDGET_REACHED)
        log.info("Step %s waits: pursuit %s reached its cap", step["id"], pursuit["id"])
        return
    abort = llm.AbortToken()
    meter = Meter(float(pursuit["cost_usd"]), float(pursuit["budget_usd"]), abort)

    def ask(prompt: Prompt, call_label: str, max_tokens: int) -> str:
        if _stopped(pursuit["id"]):
            abort.set()
            raise llm.DraftCancelled(f"{call_label}: the pursuit was closed")
        return generate(prompt.user, prompt.system, model=model, max_tokens=max_tokens, timeout=PHASE_TIMEOUT_S,
                        phase_label=call_label, abort=abort, on_usage=meter.record)

    watcher = Watcher(pursuit["id"], doing, abort)
    watcher.start()
    try:
        ctx = StepContext(pursuit=pursuit, step=step, record=inputs.gather(pursuit["id"]),
                          work_dir=WORK_ROOT / f"pursuit-{pursuit['id']}", ask=ask,
                          progress=lambda states: lq.set_task_states(step["id"], states), previous=_previous(step),
                          today=today, word_format=_word_format(pursuit["id"]))
        result = runner(ctx)
    except llm.DraftCancelled:
        if meter.over:
            lq.block_step(step["id"], BUDGET_REACHED, meter.cost)
            log.info("Step %s stopped at the cap after $%.2f", step["id"], meter.cost)
        elif not lq.stop_step(step["id"], meter.cost):
            lq.fail_step(step["id"], LEFT_WORKING, meter.cost)
        else:
            log.info("Step %s stopped: its pursuit was closed", step["id"])
        return
    except KeyboardInterrupt:
        lq.fail_step(step["id"], LEFT_WORKING, meter.cost)
        raise
    except Exception as exc:   # noqa: BLE001 (any failure is the step's, said in words on its card)
        lq.fail_step(step["id"], _why(exc), meter.cost)
        log.error("Step %s failed: %s", step["id"], type(exc).__name__)
        return
    finally:
        watcher.stop()
    if not lq.finish_step(step["id"], summary=_undashed(result.summary) or None, files=result.files or None,
                          content=_undashed(result.content) or None, cost_usd=meter.cost):
        lq.stop_step(step["id"], meter.cost)
        log.info("Step %s finished after its pursuit was closed; stopped", step["id"])
        return
    log.info("Step %s ready, $%.4f", step["id"], meter.cost)
    if not lq.needs_owner(step["step"], pursuit["approval_mode"]):
        if step["step"] == "reviews":
            # With key gates only the owner chose not to decide each step, so the reviewers' changes are accepted.
            lq.accept_open_changes(step["id"], lq.AUTO_APPROVER)
        lq.approve_step(step["id"], lq.AUTO_APPROVER)


def run_job(job: dict[str, Any]) -> None:
    """A job other than a step: Check again (PW22) scans the pursuit's newest draft. A Drive refresh waits for Drive."""
    lq.worker_beat(lq.WORKER, "working", f"{job['kind']} (job {job['id']})")
    log.info("Job %s claimed: %s, pursuit %s", job["id"], job["kind"], job["pursuit_id"])
    try:
        if job["kind"] != "slop_scan":
            lq.finish_job(job["id"], "failed", "Drive is not set up yet.")
            return
        draft = latest_draft(WORK_ROOT / f"pursuit-{job['pursuit_id']}")
        if draft is None:
            lq.finish_job(job["id"], "failed", "There is no draft to check yet.")
            return
        solicitation = slop_gate.solicitation_text(inputs.draft_inputs(inputs.gather(job["pursuit_id"])))
        found = scan.check(job["pursuit_id"], None, draft, solicitation)
        lq.finish_job(job["id"], "done" if found["scan_id"] else "failed", found["verdict"])
    except Exception as exc:   # noqa: BLE001 (the job's failure is said on the page that asked for it)
        lq.finish_job(job["id"], "failed", _why(exc))
        log.error("Job %s failed: %s", job["id"], type(exc).__name__)
    finally:
        lq.worker_beat(lq.WORKER, "idle")


def work_once(generate: Callable[..., str] | None = None, model: str | None = None, today: date | None = None) -> bool:
    """Claim the oldest queued step and run it; with no step waiting, the oldest job. False when nothing is waiting."""
    step = lq.claim_next_step()
    if step is None:
        job = lq.claim_next_job()
        if job is None:
            return False
        run_job(job)
        return True
    pursuit = lq.get_pursuit(step["pursuit_id"])
    assert pursuit is not None
    label = lq.STEP_LABELS.get(step["step"], step["step"])
    doing = f"{label} (pursuit {pursuit['id']})"
    log.info("Step %s claimed: %s, attempt %s, pursuit %s", step["id"], step["step"], step["attempt"], pursuit["id"])
    lq.worker_beat(lq.WORKER, "working", doing)
    try:
        _run(step, pursuit, label, doing, generate or llm.generate, model or llm.DEFAULT_MODEL, today or date.today())
    finally:
        lq.worker_beat(lq.WORKER, "idle")
    return True


# ------------------------------------------------------------------------------ serving

def recover() -> int:
    """Fail every step a stopped worker left working, with Retry for the owner. Only one worker runs, so a
    working step at start has nobody working on it."""
    left = lq.steps_in_state("working")
    for step in left:
        lq.fail_step(step["id"], LEFT_WORKING)
    return len(left)


def serve(once: bool = False, poll_s: float = POLL_S, generate: Callable[..., str] | None = None,
          stop: threading.Event | None = None) -> int:
    """Run steps until stopped, or one with once. Returns the exit code."""
    stop = stop or threading.Event()
    try:
        take_lock()
    except WorkerRunning as exc:
        log.info("%s", exc)
        return 0
    try:
        lq.worker_started(lq.WORKER)
        left = recover()
        if left:
            log.warning("Failed %d step(s) a stopped worker left working", left)
        while not stop.is_set():
            try:
                ran = work_once(generate=generate)
            except Exception as exc:   # noqa: BLE001 (the ledger may be unreachable: say so, wait, try again)
                log.error("Could not work: %s", type(exc).__name__)
                ran = False
            if once:
                break
            if not ran:
                stop.wait(poll_s)
                try:
                    lq.worker_beat(lq.WORKER, "idle")
                except Exception as exc:   # noqa: BLE001
                    log.warning("Heartbeat failed: %s", type(exc).__name__)
        return 0
    finally:
        try:
            lq.worker_beat(lq.WORKER, "stopped")
        except Exception as exc:   # noqa: BLE001
            log.warning("Could not record the stop: %s", type(exc).__name__)
        release_lock()


def setup_logging(debug: bool = False) -> Path:
    """data/drafting/logs/worker.log, a new file each midnight, a month kept."""
    log_dir = DATA_DIR / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    path = log_dir / "worker.log"
    handlers: list[logging.Handler] = [
        logging.handlers.TimedRotatingFileHandler(path, when="midnight", backupCount=30, encoding="utf-8", delay=True)]
    if sys.stderr is not None:   # none under pythonw, as Task Scheduler runs it
        handlers.append(logging.StreamHandler(sys.stderr))
    logging.basicConfig(level=logging.DEBUG if debug else logging.INFO, handlers=handlers, force=True,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m drafting.worker",
                                     description="Run the proposal workspace's steps (docs/RUNBOOK.md, The worker)")
    parser.add_argument("--once", action="store_true", help="run at most one queued step, then exit")
    parser.add_argument("--debug", action="store_true", help="log full prompts (DEBUG); never in production")
    args = parser.parse_args(argv)
    setup_logging(debug=args.debug)
    try:
        return serve(once=args.once)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    sys.exit(main())
