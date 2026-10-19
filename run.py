"""The pipeline: fetch every portal, filter, review, digest. One command, schedulable.

    python run.py                          # every registered portal
    python run.py --portal vulcan_sof      # one portal
    python run.py --dry-run                # everything runs, nothing is committed
    python run.py --skip-fetch             # no browser; filter and review rows still pending
    python run.py --no-review              # kept rows get verdict "maybe", reasoning "LLM review disabled"
    python run.py --limit 5                # cap scraped and reviewed rows
    python run.py --fetch-timeout 10       # override every portal's fetch budget (testing)
    python run.py --feedback-only          # Slack thread notes in, decisions out to the cards, nothing else
    python run.py --deliver-run 12         # re-post run 12's cards after a Slack failure
    python run.py --wait-lock 30           # if another run holds the lock, wait up to 30 minutes for it

The portal assistant's scheduled jobs (docs/ASSISTANT.md) also run from here, because this
is the one place that wires components together (AGENTS.md, hard rule 1):

    python run.py --remind                 # Slack: calls marked Pursue and due within 14 days
    python run.py --post-summary           # Slack: each portal's week and its scraper health
    python run.py --apply-requests         # carry out change requests approved on the dashboard

A lock file (data/pipeline.lock) stops two pipelines running at once; --apply-requests takes
it too, and only when an approved request is ready. The fetch stage runs in a worker thread
under a hard timeout; on expiry the browser is force-closed and the run is recorded as
skipped_timeout, and later stages still run on whatever was saved. Every run writes
data/logs/run_YYYY-MM-DD_HHMM.log and a `runs` row.
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import config
from ledger.db import dry_run_session
from ledger.queries import (
    calls_where,
    claim_request,
    finish_request,
    finish_run,
    get_call,
    get_run,
    list_requests,
    new_calls,
    note_request,
    set_review,
    start_run,
)
from portals import registry
from portals.registry import Portal

REPO_ROOT = Path(__file__).resolve().parent
DATA_DIR = REPO_ROOT / "data"
LOCK_FILE = DATA_DIR / "pipeline.lock"
LOG_DIR = DATA_DIR / "logs"
STALE_LOCK_S = 2 * 60 * 60
FORCE_CLOSE_GRACE_S = 10
NO_REVIEW_REASON = "LLM review disabled"
VERDICT_ORDER = {"yes": 0, "maybe": 1}
BAD_PAGES_MIN = 3          # alert when at least this many pages read badly...
BAD_PAGES_SHARE = 0.10     # ...and at least this share of the scan
LOCK_POLL_S = 15
REMIND_DAYS = 14
APPLY_KINDS = ("keyword_change", "rereview", "scan", "fault_report")   # drafts belong to the Writer
SETTINGS_BRANCH = "main"
GIT_TIMEOUT_S = 60
ISSUE_TIMEOUT_S = 120
GITHUB_TOKEN_KEY = "BD_GITHUB_TOKEN"   # the pipeline's own GitHub token; see "GitHub token" in docs/RUNBOOK.md

log = logging.getLogger("pipeline")


# ------------------------------------------------------------------------------- lock

class LockHeld(RuntimeError):
    pass


def _pid_alive(pid: int) -> bool:
    if sys.platform == "win32":
        # os.kill(pid, 0) would TERMINATE the process on Windows; ask tasklist instead.
        try:
            out = subprocess.run(["tasklist", "/FI", f"PID eq {pid}", "/NH"], capture_output=True, text=True, timeout=15)
            return str(pid) in out.stdout
        except Exception:
            return True
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_lock(path: Path | None = None, wait_s: float = 0, poll_s: float = LOCK_POLL_S) -> None:
    """Take the pipeline lock. While another live run holds it, wait up to wait_s, then raise LockHeld."""
    path = path or LOCK_FILE   # resolved at call time so tests can redirect it
    deadline = time.time() + wait_s
    while True:
        try:
            _take_lock(path)
            return
        except LockHeld:
            left = deadline - time.time()
            if left <= 0:
                raise
            log.info("Lock held; waiting up to %.0f more seconds", left)
            time.sleep(min(poll_s, left))


def _take_lock(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        age: float | None = time.time() - path.stat().st_mtime
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:   # no lock, or its holder just released it
        age, text = None, ""
    if age is not None:
        try:
            holder = int(text.split()[0])
        except (ValueError, IndexError):
            holder = -1
        if age < STALE_LOCK_S and holder > 0 and _pid_alive(holder):
            raise LockHeld(f"Another pipeline is running (pid {holder}, lock {path}). Not starting.")
        log.warning("Removing stale lock from pid %s (%.0f min old)", holder, age / 60)
        path.unlink(missing_ok=True)
    path.write_text(f"{os.getpid()} {datetime.now(timezone.utc).isoformat()}\n", encoding="utf-8")


def release_lock(path: Path | None = None) -> None:
    path = path or LOCK_FILE
    try:
        path.unlink(missing_ok=True)
    except OSError:
        pass


# ---------------------------------------------------------------------------- logging

def setup_logging(log_dir: Path | None = None, debug: bool = False) -> Path:
    log_dir = log_dir or LOG_DIR
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    path = log_dir / f"run_{stamp}.log"
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.DEBUG if debug else logging.INFO)
    for handler in list(root.handlers):
        root.removeHandler(handler)
    for handler in (logging.StreamHandler(sys.stdout), logging.FileHandler(path, encoding="utf-8")):
        handler.setFormatter(fmt)
        root.addHandler(handler)
    for noisy in ("httpx2", "httpcore2", "httpx", "httpcore", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return path


# ----------------------------------------------------------------------------- stages

def run_fetch(portal: Portal, run_id: int, timeout_s: int, limit: int | None) -> tuple[str, dict[str, int], str | None]:
    """Run the portal's fetch in a worker thread. Returns (status, counts, error)."""
    result: dict[str, Any] = {}

    def worker() -> None:
        try:
            if portal.needs_browser:
                from portals.shared.browser import close_all, launch

                pw, browser, context, page = launch()
                try:
                    result["counts"] = portal.fetch(page, run_id, limit=limit)
                finally:
                    close_all(pw, browser, context, page)
            else:
                result["counts"] = portal.fetch(None, run_id, limit=limit)
        except BaseException as exc:   # noqa: BLE001  (recorded, never propagated)
            result["error"] = exc
            result["trace"] = traceback.format_exc()

    thread = threading.Thread(target=worker, name=f"fetch-{portal.slug}", daemon=True)
    thread.start()
    thread.join(timeout_s)
    empty = {"found": 0, "scraped": 0, "new": 0, "failed": 0}

    if thread.is_alive():
        log.error("FETCH TIMEOUT: %s exceeded %ds, skipping", portal.name, timeout_s)
        from portals.shared.browser import force_close

        force_close()
        thread.join(FORCE_CLOSE_GRACE_S)
        return "skipped_timeout", empty, f"fetch exceeded {timeout_s}s"
    if "error" in result:
        exc = result["error"]
        message = f"{type(exc).__name__}: {str(exc)[:200]}"
        log.error("FETCH ERROR: %s: %s", portal.name, message)
        log.debug("%s", result.get("trace", ""))
        return "error", empty, message
    return "completed", dict(result["counts"]), None


def watch_quality(portal: Portal, run_id: int, log_path: Path) -> None:
    """Alert when a completed scan read too many pages badly (no deadline or description found)."""
    from assistant.tools import fetch_quality

    quality = fetch_quality(run_id)
    if quality["count"] >= max(BAD_PAGES_MIN, math.ceil(BAD_PAGES_SHARE * quality["total"])):
        alert(f"velocity-bd-team: {portal.name} scan read {quality['count']} of {quality['total']} pages badly "
              f"(no deadline or description found), for example: {', '.join(quality['examples'])}. "
              f"The page layout may have changed. Log: {log_path}")


def run_filter(portal: Portal) -> int:
    pending = calls_where(portal=portal.name, filter_result="pending")
    if pending:
        portal.filter(pending)
    return len(pending)


def run_review(portal: Portal, limit: int | None, no_review: bool) -> int:
    rows = calls_where(portal=portal.name, filter_result="kept", reviewed=False)
    if limit is not None:
        rows = rows[:limit]
    if not rows:
        return 0
    if no_review:
        for row in rows:
            set_review(row["id"], "maybe", NO_REVIEW_REASON)
        return len(rows)
    from review.feedback import build_examples_block
    from review.reviewer import review_calls

    examples = build_examples_block()
    log.info("REVIEW: feedback examples block is %d chars", len(examples))
    review_calls(rows, review_model(), feedback_examples_block=examples)
    return len(rows)


def review_model() -> Any:
    """The reviewer's model client. Tests replace this with a scripted one."""
    from review.reviewer import AnthropicModel

    return AnthropicModel()


def deliver(portal: Portal, fresh: list[dict[str, Any]], counts: dict[str, int], elapsed: float, dry_run: bool) -> int:
    """Post one card per new call and a run summary. In dry-run, print the cards instead."""
    from slack.sink import card_text, post_call, post_run_summary

    if dry_run:
        print(f"\n===== DRY RUN: would post {len(fresh)} card(s) to Slack =====")
        for row in fresh:
            print(card_text(row))
            print()
        return 0
    posted = sum(1 for row in fresh if post_call(row))
    post_run_summary({
        "portal": portal.name,
        "scanned": counts.get("fetched", 0),
        "new": len(fresh),
        "yes": sum(1 for r in fresh if r.get("ai_verdict") == "yes"),
        "maybe": sum(1 for r in fresh if r.get("ai_verdict") == "maybe"),
        "elapsed": elapsed,
    })
    return posted


def redeliver(run_id: int) -> int:
    """Post the cards of a run whose Slack delivery failed (rows still without slack_ts)."""
    from slack.sink import post_call, post_run_summary

    run = get_run(run_id)
    if run is None:
        print(f"no run {run_id}")
        return 2
    pending = [r for r in new_calls(run_id) if not r.get("slack_ts")]
    posted = sum(1 for row in pending if post_call(row))
    counts = json.loads(run.get("stage_counts") or "{}")
    post_run_summary({
        "portal": run.get("portal") or "Pipeline",
        "scanned": counts.get("fetched", 0),
        "new": len(pending),
        "yes": sum(1 for r in pending if r.get("ai_verdict") == "yes"),
        "maybe": sum(1 for r in pending if r.get("ai_verdict") == "maybe"),
        "elapsed": 0.0,
    })
    print(f"deliver-run {run_id}: {posted} of {len(pending)} card(s) posted")
    return 0 if posted == len(pending) else 1


def feedback_pass(dry_run: bool) -> list[dict[str, Any]]:
    """Pull Slack thread notes into the ledger and edit cards to show decisions. Skipped in dry-run."""
    if dry_run:
        log.info("FEEDBACK: skipped (--dry-run makes no Slack calls)")
        return []
    from slack.sink import collect_feedback

    t0 = time.time()
    changes = collect_feedback()
    log.info("FEEDBACK: %d change(s) (%.1fs)", len(changes), time.time() - t0)
    for c in changes:
        print(f"  feedback: {c['id']} | {c['title'][:60]} | notes={len(c['notes'])} card_updated={'yes' if c['card_updated'] else 'no'}")
    return changes


def digest_lines(rows: list[dict[str, Any]]) -> list[str]:
    ordered = sorted(rows, key=lambda r: (VERDICT_ORDER.get(r.get("ai_verdict") or "", 9), r.get("due_date") or "~"))
    lines: list[str] = []
    for r in ordered:
        lines.append(
            f"[{(r.get('ai_verdict') or '?').upper():5s}] {r.get('title') or ''}\n"
            f"        due: {r.get('due_date') or 'n/a'}\n"
            f"        {r.get('url') or ''}\n"
            f"        {r.get('ai_reasoning') or ''}"
        )
    return lines


def print_digest(portal_name: str, rows: list[dict[str, Any]]) -> None:
    print(f"\n===== DIGEST: {portal_name}: {len(rows)} new call(s) =====")
    for line in digest_lines(rows):
        print(line)
    if not rows:
        print("(nothing new)")


def alert(text: str) -> None:
    try:
        from slack.alerts import send_alert

        send_alert(text)
    except Exception as exc:   # alerts must never take the pipeline down
        log.warning("Alert failed: %s: %s", type(exc).__name__, str(exc)[:120])


# ------------------------------------------------------------ assistant: scheduled posts

def _console_logging() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def remind() -> int:
    """Post the calls marked Pursue and due within REMIND_DAYS. Posts nothing when none are due."""
    from assistant.tools import upcoming_deadlines
    from slack.sink import post_text

    _console_logging()
    result = upcoming_deadlines(days=REMIND_DAYS)
    if not result["calls"]:
        print(f"No Pursue deadlines in the next {REMIND_DAYS} days; nothing to post.")
        return 0
    ts = post_text("*Deadline reminder*\n" + result["text"])
    print(f"Posted {len(result['calls'])} reminder(s)" + ("" if ts else " (Slack did not accept the post; see the log)"))
    return 0 if ts else 1


def post_summary() -> int:
    """Post each portal's weekly summary and scraper health as one message."""
    from assistant.tools import scraper_health, weekly_summary
    from slack.sink import post_text

    _console_logging()
    parts = [f"{weekly_summary(p.slug)['text']}\nScraper: {scraper_health(p.slug)['text']}" for p in registry.discover()]
    if not parts:
        print("No portals registered; nothing to post.")
        return 0
    ts = post_text("\n\n".join(parts))
    print("Posted the weekly summary" + ("" if ts else " (Slack did not accept the post; see the log)"))
    return 0 if ts else 1


# ------------------------------------------------------- assistant: approved change requests
# A propose tool records a request, a person approves it on the dashboard, and this carries
# it out (docs/ASSISTANT.md, "Approvals"). An approved request that cannot run yet stays
# approved with a "Waiting: ..." note and is tried again on the next pass.

def today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def git(cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, timeout=GIT_TIMEOUT_S)


def settings_waiting(path: Path) -> str | None:
    """Why an approved settings change cannot be committed yet, or None when it can."""
    if shutil.which("git") is None:
        return "Waiting: git is not installed on the scan machine."
    branch = git(path.parent, "rev-parse", "--abbrev-ref", "HEAD")
    if branch.returncode != 0:
        return f"Waiting: {path.name} is not in a git checkout."
    name = branch.stdout.strip()
    if name != SETTINGS_BRANCH:
        return (f"Waiting: the scan machine is on branch {name}; approved settings are committed on "
                f"{SETTINGS_BRANCH} only.")
    if git(path.parent, "status", "--porcelain", "--", path.name).stdout.strip():
        return f"Waiting: {path.name} has uncommitted edits on the scan machine; commit or discard them first."
    return None


def github_waiting() -> str | None:
    """Why a fault report cannot be filed yet, or None when it can."""
    remote = git(REPO_ROOT, "remote", "get-url", "origin")
    if remote.returncode != 0 or "github.com" not in remote.stdout:
        return "Waiting: this repo has no GitHub remote yet, so the issue cannot be filed."
    if shutil.which("gh") is None:
        return "Waiting: the GitHub command line tool (gh) is not installed on the scan machine."
    return None


def github_env() -> dict[str, str] | None:
    """Environment for gh: the pipeline's own token when .env has one, else None so gh uses the signed-in login."""
    token = config.get(GITHUB_TOKEN_KEY)
    return {**os.environ, "GH_TOKEN": token} if token else None


def file_issue(title: str, body: str) -> str:
    """File a GitHub issue in this repo with gh. Returns the issue's URL.

    gh files it with the pipeline's own token (BD_GITHUB_TOKEN) when .env has one, and with
    whoever is signed in to gh otherwise. See "GitHub token" in docs/RUNBOOK.md.
    """
    env = github_env()
    done = subprocess.run(["gh", "issue", "create", "--title", title, "--body", body], cwd=REPO_ROOT,
                          capture_output=True, text=True, timeout=ISSUE_TIMEOUT_S, env=env)
    if done.returncode != 0:
        error = (done.stderr or done.stdout).strip()
        if env and ("401" in error or "Bad credentials" in error):
            raise RuntimeError(f"GitHub refused the pipeline token in {GITHUB_TOKEN_KEY}; it has probably expired. "
                               "Create a new one (see GitHub token in docs/RUNBOOK.md) and replace it in .env.")
        if env and ("403" in error or "not accessible" in error):
            raise RuntimeError(f"The pipeline token in {GITHUB_TOKEN_KEY} cannot file issues here. A classic token "
                               "needs the repo scope; a fine-grained one needs Issues: Read and write on "
                               "velocity-bd-team (see GitHub token in docs/RUNBOOK.md).")
        raise RuntimeError(f"gh issue create failed: {error[:200]}")
    return done.stdout.strip().splitlines()[-1]


def _payload(req: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(req.get("payload") or "{}")
    except ValueError:
        return {}
    return data if isinstance(data, dict) else {}


def request_waiting(req: dict[str, Any]) -> str | None:
    """Why an approved request cannot be carried out yet, or None when it can."""
    if req["kind"] == "keyword_change":
        try:
            portal = registry.get(req["portal"] or "")
        except KeyError:
            return None   # carrying it out records the failure
        return settings_waiting(portal.keywords) if portal.keywords else None
    if req["kind"] == "fault_report":
        return github_waiting()
    return None


def apply_keyword_change(req: dict[str, Any]) -> str:
    """Edit and commit the portal's keywords file, filter its stored calls again, review the newly kept."""
    from portals.shared.keyword_filter import CHANGE_KEYS, describe_changes, edit_keywords_text

    portal = registry.get(req["portal"] or "")
    path = portal.keywords
    if path is None:
        raise RuntimeError(f"{portal.name} has no keywords file.")
    asked = _payload(req).get("changes") or {}
    changes = {key: list(asked.get(key) or []) for key in CHANGE_KEYS}
    raw = path.read_bytes().decode("utf-8")
    crlf = "\r\n" in raw
    before = raw.replace("\r\n", "\n")
    after = edit_keywords_text(before, changes,
                               note=f"added {today()} by request #{req['id']}, approved by {req['decided_by']}")
    if after == before:
        return f"Nothing to change: {path.name} already matches."
    path.write_bytes((after.replace("\n", "\r\n") if crlf else after).encode("utf-8"))
    by = f"(request #{req['id']}, approved by {req['decided_by']})"
    subject = f"chore({portal.slug}): {describe_changes(changes)} {by}"
    if len(subject) > 120:
        subject = f"chore({portal.slug}): keyword changes {by}"
    done = git(path.parent, "commit", "-q", "-m", subject, "--", path.name)
    if done.returncode != 0:
        path.write_bytes(raw.encode("utf-8"))   # leave the file as it was
        raise RuntimeError(f"git commit failed: {(done.stderr or done.stdout).strip()[:200]}")
    sha = git(path.parent, "rev-parse", "--short", "HEAD").stdout.strip()

    stored = calls_where(portal=portal.name)
    was = {r["id"]: r["filter_result"] for r in stored}
    if stored:
        portal.filter(stored)
    now = {r["id"]: r["filter_result"] for r in calls_where(portal=portal.name)}
    kept = sum(1 for cid, result in now.items() if result == "kept" and was.get(cid) != "kept")
    dropped = sum(1 for cid, result in now.items() if result != "kept" and was.get(cid) == "kept")
    reviewed = run_review(portal, None, no_review=False)
    return (f"Committed {sha} to {SETTINGS_BRANCH}. Filtered {len(stored)} stored calls again: {kept} newly kept, "
            f"{dropped} newly dropped" + (f"; reviewed {reviewed}." if reviewed else "."))


def apply_rereview(req: dict[str, Any]) -> str:
    """Ask the reviewer again about one call, with the team's context in the prompt."""
    from review.feedback import build_examples_block
    from review.reviewer import review_calls

    row = get_call(req["call_id"] or "")
    if row is None:
        raise RuntimeError(f"No call with id '{req['call_id']}'.")
    before = row.get("ai_verdict")
    passed, dropped = review_calls([row], review_model(), feedback_examples_block=build_examples_block(),
                                   extra_context=str(_payload(req).get("context") or ""))
    result = (passed + dropped)[0]
    if before and before != result.verdict:
        change = f"changed from {before} to {result.verdict}"
    elif before:
        change = f"stayed {result.verdict}"
    else:
        change = f"said {result.verdict}"
    return f"The AI review {change}: {result.reason}"


def apply_scan(req: dict[str, Any], log_path: Path) -> tuple[str, bool]:
    """One pipeline run for the portal, as `run.py --portal <slug>` would do it."""
    portal = registry.get(req["portal"] or "")
    feedback_pass(dry_run=False)
    outcome = run_portal(portal, parse_args(["--portal", portal.slug]), log_path)
    counts = outcome["counts"]
    text = (f"Run #{outcome['run_id']} {outcome['status']}: fetched {counts.get('fetched', 0)}, filtered "
            f"{counts.get('filtered', 0)}, reviewed {counts.get('reviewed', 0)}, {counts.get('new', 0)} new.")
    run = get_run(outcome["run_id"]) or {}
    if run.get("error"):
        text += f" {run['error']}"
    return text, outcome["status"] == "completed"


def apply_fault_report(req: dict[str, Any]) -> str:
    data = _payload(req)
    body = f"{str(data.get('body') or '').rstrip()}\n\nApproved by {req['decided_by']} (request #{req['id']})."
    return f"Filed {file_issue(str(data.get('title') or req['summary']), body)}"


def carry_out(req: dict[str, Any], log_path: Path) -> tuple[str, bool]:
    if req["kind"] == "keyword_change":
        return apply_keyword_change(req), True
    if req["kind"] == "rereview":
        return apply_rereview(req), True
    if req["kind"] == "scan":
        return apply_scan(req, log_path)
    if req["kind"] == "fault_report":
        return apply_fault_report(req), True
    raise RuntimeError(f"run.py does not carry out {req['kind']} requests.")


def _failure_text(exc: BaseException) -> str:
    if isinstance(exc, KeyError) and exc.args:
        return str(exc.args[0])
    if isinstance(exc, (RuntimeError, ValueError)):
        return str(exc)
    return f"{type(exc).__name__}: {exc}"[:500]


def report_outcomes(outcomes: list[tuple[dict[str, Any], str, str]]) -> None:
    if not outcomes:
        return
    lines = ["*Approved requests carried out*"]
    for req, status, text in outcomes:
        lines.append(f"- #{req['id']} {req['summary']} (approved by {req.get('decided_by') or 'someone'}): "
                     f"{'done' if status == 'applied' else 'failed'}. {text}")
    try:
        from slack.sink import post_text

        post_text("\n".join(lines))
    except Exception as exc:   # the ledger already holds every outcome
        log.warning("Slack post of request outcomes failed: %s: %s", type(exc).__name__, str(exc)[:120])


def apply_requests(wait_s: float = 0) -> int:
    """Carry out approved requests, oldest first. 0 when all went well or nothing was ready,
    1 when one failed, 3 when another run holds the lock (they stay approved for next time)."""
    approved = [r for r in list_requests("approved", limit=100, oldest_first=True) if r["kind"] in APPLY_KINDS]
    stuck = list_requests("applying", limit=100, oldest_first=True)
    ready = []
    for req in approved:
        waiting = request_waiting(req)
        if waiting is None:
            ready.append(req)
            continue
        if waiting != req.get("result"):
            note_request(req["id"], waiting)
        print(f"request #{req['id']}: {waiting}")
    if not ready and not stuck:
        print("No approved requests to carry out." if not approved else "Nothing to carry out now.")
        return 0
    try:
        acquire_lock(wait_s=wait_s)
    except LockHeld as exc:
        print(f"{exc} Approved requests stay approved for the next pass.")
        return 3
    try:
        log_path = setup_logging()
        outcomes: list[tuple[dict[str, Any], str, str]] = []
        for req in stuck:   # we hold the lock, so nothing else is carrying these out
            text = "Interrupted: the job stopped before it finished. Propose it again if it is still needed."
            if finish_request(req["id"], "failed", text):
                outcomes.append((req, "failed", text))
        for req in ready:
            if not claim_request(req["id"]):
                continue
            log.info("REQUEST #%d (%s): %s", req["id"], req["kind"], req["summary"])
            try:
                text, ok = carry_out(req, log_path)
            except Exception as exc:
                text, ok = _failure_text(exc), False
                log.debug("%s", traceback.format_exc())
            status = "applied" if ok else "failed"
            finish_request(req["id"], status, text)
            log.info("REQUEST #%d %s: %s", req["id"], status, text)
            outcomes.append((req, status, text))
        report_outcomes(outcomes)
        for req, status, text in outcomes:
            print(f"request #{req['id']} {status}: {text}")
        return 0 if all(status == "applied" for _, status, _ in outcomes) else 1
    finally:
        release_lock()


# ----------------------------------------------------------------------------- portal

def run_portal(portal: Portal, args: argparse.Namespace, log_path: Path) -> dict[str, Any]:
    started = time.time()
    run_id = start_run(portal.name, dry_run=args.dry_run, component=portal.slug)
    log.info("=== %s: run %d started%s ===", portal.name, run_id, " (DRY RUN)" if args.dry_run else "")
    counts = {"fetched": 0, "filtered": 0, "reviewed": 0, "new": 0}
    status, error = "completed", None
    timeout_s = args.fetch_timeout or portal.fetch_timeout

    try:
        if args.skip_fetch:
            log.info("FETCH: skipped (--skip-fetch)")
        else:
            t0 = time.time()
            status, fetch_counts, error = run_fetch(portal, run_id, timeout_s, args.limit)
            counts["fetched"] = fetch_counts.get("scraped", 0)
            log.info("FETCH: %d rows (%.1fs) status=%s", counts["fetched"], time.time() - t0, status)
            if status != "completed":
                alert(f"velocity-bd-team: {portal.name} fetch {status}. {error}. Log: {log_path}")
            elif not args.dry_run:
                watch_quality(portal, run_id, log_path)

        t0 = time.time()
        counts["filtered"] = run_filter(portal)
        log.info("FILTER: %d rows (%.1fs)", counts["filtered"], time.time() - t0)

        t0 = time.time()
        counts["reviewed"] = run_review(portal, args.limit, args.no_review)
        log.info("REVIEW: %d rows (%.1fs)", counts["reviewed"], time.time() - t0)

        fresh = new_calls(run_id)
        counts["new"] = len(fresh)
        log.info("NEW: %d rows", counts["new"])
        print_digest(portal.name, fresh)

        t0 = time.time()
        posted = deliver(portal, fresh, counts, time.time() - started, args.dry_run)
        log.info("DELIVER: %d card(s) (%.1fs)", posted, time.time() - t0)
    except Exception as exc:
        status, error = "error", f"{type(exc).__name__}: {str(exc)[:200]}"
        log.error("PIPELINE ERROR in %s: %s", portal.name, error)
        log.debug("%s", traceback.format_exc())
        alert(f"velocity-bd-team: {portal.name} pipeline error. {error}. Log: {log_path}")
    finally:
        finish_run(run_id, status, counts, error=error, log_path=str(log_path))
    log.info("=== %s: run %d %s in %.0fs: %s ===", portal.name, run_id, status, time.time() - started, counts)
    return {"portal": portal.name, "run_id": run_id, "status": status, "counts": counts}


def run_all(portals_to_run: list[Portal], args: argparse.Namespace, log_path: Path) -> list[dict[str, Any]]:
    return [run_portal(p, args, log_path) for p in portals_to_run]


# ------------------------------------------------------------------------------- main

def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="velocity-bd-team pipeline")
    parser.add_argument("--portal", help="run a single portal by slug")
    parser.add_argument("--dry-run", action="store_true", help="run everything, commit nothing")
    parser.add_argument("--skip-fetch", action="store_true", help="skip the browser; filter and review pending rows")
    parser.add_argument("--no-review", action="store_true", help="skip the LLM; kept rows become 'maybe'")
    parser.add_argument("--limit", type=int, help="cap scraped and reviewed rows")
    parser.add_argument("--fetch-timeout", type=int, help="override the per-portal fetch timeout in seconds")
    parser.add_argument("--feedback-only", action="store_true", help="only sync Slack: thread notes in, decisions out to the cards")
    parser.add_argument("--debug", action="store_true", help="DEBUG logging (includes the first review prompt)")
    parser.add_argument("--deliver-run", type=int, metavar="N", help="re-post run N's new calls that never reached Slack, then exit")
    parser.add_argument("--wait-lock", type=int, default=0, metavar="MINUTES",
                        help="if another run holds the lock, wait up to this many minutes for it")
    parser.add_argument("--remind", action="store_true", help="post Slack reminders for Pursue calls due soon, then exit")
    parser.add_argument("--post-summary", action="store_true", help="post the weekly summary to Slack, then exit")
    parser.add_argument("--apply-requests", action="store_true",
                        help="carry out change requests approved on the dashboard, then exit")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.remind:
        return remind()
    if args.post_summary:
        return post_summary()
    if args.apply_requests:
        return apply_requests(wait_s=args.wait_lock * 60)
    try:
        acquire_lock(wait_s=args.wait_lock * 60)
    except LockHeld as exc:
        print(exc)
        return 3
    try:
        log_path = setup_logging(debug=args.debug)
        log.info("Pipeline start; log %s; args %s", log_path, vars(args))
        if args.feedback_only:
            changes = feedback_pass(dry_run=False)
            print(f"feedback-only: {len(changes)} change(s) recorded")
            return 0
        if args.deliver_run:
            return redeliver(args.deliver_run)
        portals_to_run = [registry.get(args.portal)] if args.portal else registry.discover()
        if not portals_to_run:
            log.error("No portals registered under portals/")
            return 1
        feedback_pass(args.dry_run)   # before review, so this run's prompt sees the newest decisions
        if args.dry_run:
            with dry_run_session():
                results = run_all(portals_to_run, args, log_path)
            log.info("DRY RUN: all ledger writes rolled back")
            print("\nDRY RUN: nothing was committed. Would have written:")
        else:
            results = run_all(portals_to_run, args, log_path)
            print("\nSummary:")
        for r in results:
            print(f"  {r['portal']}: run {r['run_id']} {r['status']} {r['counts']}")
        return 0 if all(r["status"] == "completed" for r in results) else 1
    except KeyError as exc:
        print(exc)
        return 2
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())
