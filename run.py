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

A lock file (data/pipeline.lock) stops two pipelines running at once. The fetch stage runs
in a worker thread under a hard timeout; on expiry the browser is force-closed and the run
is recorded as skipped_timeout, and later stages still run on whatever was saved. Every run
writes data/logs/run_YYYY-MM-DD_HHMM.log and a `runs` row.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ledger.db import dry_run_session
from ledger.queries import calls_where, finish_run, get_run, new_calls, set_review, start_run
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


def acquire_lock(path: Path | None = None) -> None:
    path = path or LOCK_FILE   # resolved at call time so tests can redirect it
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        age = time.time() - path.stat().st_mtime
        try:
            holder = int(path.read_text(encoding="utf-8").split()[0])
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
    from review.reviewer import AnthropicModel, review_calls

    examples = build_examples_block()
    log.info("REVIEW: feedback examples block is %d chars", len(examples))
    review_calls(rows, AnthropicModel(), feedback_examples_block=examples)
    return len(rows)


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
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        acquire_lock()
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
