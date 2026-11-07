"""The pipeline: fetch every portal, filter, review, digest. One command, schedulable.

    python run.py                          # every registered portal
    python run.py --portal vulcan_sof      # one portal
    python run.py --dry-run                # everything runs, nothing is committed
    python run.py --skip-fetch             # no browser; filter and review rows still pending
    python run.py --no-review              # kept rows get verdict "maybe", reasoning "LLM review disabled"
    python run.py --limit 5                # cap scraped and reviewed rows
    python run.py --fetch-timeout 10       # override every portal's fetch budget (testing)
    python run.py --feedback-only          # Slack thread notes in, decisions out to the cards, nothing else
    python run.py --deliver-run 12         # post run 12's Slack summary, held or lost to a Slack failure
    python run.py --hold-slack             # judge and save as usual, post no summary; --deliver-run posts it later
    python run.py --linear-sync            # issues in Linear's Pursuits project for the calls the team pursues
    python run.py --wait-lock 30           # if another run holds the lock, wait up to 30 minutes for it

The portal assistant's scheduled jobs (docs/ASSISTANT.md) also run from here, because this
is the one place that wires components together (AGENTS.md, hard rule 1):

    python run.py --remind                 # Slack: calls marked Pursue and due within 14 days
    python run.py --post-summary           # Slack: each portal's week and its scraper health (and the brief)
    python run.py --write-brief            # the dashboard's Monday brief for this week, no Slack post
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
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import config
from ledger.db import dry_run_session
from ledger.db import release as release_connection
from ledger.queries import (
    calls_where,
    claim_request,
    finish_request,
    finish_run,
    get_call,
    get_run,
    judge_records,
    save_brief,
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
BRIEF_TOP = 10              # calls in the Monday brief's Top 10 across portals
BRIEF_AUTHOR = "pipeline"   # briefs.written_by; a portal's bot may write its own brief later
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
        finally:
            release_connection()   # the thread's reused ledger connection (PRO-550)

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
    second_judge(rows, examples)
    return len(rows)


def run_summaries(portal: Portal, no_review: bool) -> int:
    """Summaries for this portal's calls the review did not summarize, the keyword filter's rejects above all (phase
    9c); the review writes the rest in the answer it already gives. --no-review asks no model."""
    from ledger.queries import calls_without_summary
    from review.reviewer import summarize_calls

    rows = calls_without_summary(portal.name)
    if no_review or not rows:
        return 0
    return summarize_calls(rows, review_model())


def review_model() -> Any:
    """The reviewer's model client. Tests replace this with a scripted one."""
    from review.reviewer import AnthropicModel

    return AnthropicModel()


GROK_KEY = "BD_XAI_API_KEY"   # the second judge's key; without it only Claude judges


def grok_enabled() -> bool:
    return bool((config.get(GROK_KEY) or "").strip())


def grok_model() -> Any:
    """The second judge's model client. Tests replace this with a scripted one."""
    from review.reviewer import GrokModel

    return GrokModel()


def second_judge(rows: list[dict[str, Any]], examples: str, extra_context: str = "") -> int:
    """Grok judges the same calls with the review's own prompt (judgments table). It never changes
    what is posted, and a failure only logs a warning: the run carries on."""
    if not rows or not grok_enabled():
        return 0
    from review.reviewer import judge_calls

    try:
        judged = judge_calls(rows, grok_model(), "grok", feedback_examples_block=examples, extra_context=extra_context)
    except Exception as exc:
        log.warning("SECOND JUDGE: skipped (%s)", type(exc).__name__)
        return 0
    log.info("SECOND JUDGE: Grok judged %d of %d call(s)", len(judged), len(rows))
    return len(judged)


def tag_by_rules(run_id: int) -> int:
    """Tag every call this run saw with the tags its own data makes certain (review/tags.py), so
    they follow the data, after writing the tag list the dashboard reads. Returns how many calls
    were tagged."""
    from ledger.queries import calls_in_run, save_tag_list, set_tags
    from review.tags import catalog, rule_tags, tag_list

    save_tag_list(catalog(tag_list()))
    seen = calls_in_run(run_id)
    for row in seen:
        set_tags(row["id"], "rule", rule_tags(row, tag_list()))
    return len(seen)


def backfill_tags() -> int:
    """Tag every stored call by its rules, then have Claude and Grok tag the kept, reviewed calls they
    have not tagged yet, asking for tags alone. Safe to rerun: each pass only fills what is missing."""
    from ledger.queries import calls_where, calls_without_tags, save_tag_list, set_tags
    from review.reviewer import tag_calls
    from review.tags import catalog, rule_tags, tag_list

    _console_logging()
    save_tag_list(catalog(tag_list()))
    stored = calls_where()
    for row in stored:
        set_tags(row["id"], "rule", rule_tags(row, tag_list()))
    print(f"Rules tagged {len(stored)} call(s).")
    pending = calls_without_tags("claude")
    print(f"Claude tagged {tag_calls(pending, review_model(), 'claude')} of {len(pending)} call(s).")
    pending = calls_without_tags("grok")
    if not grok_enabled():
        print(f"{GROK_KEY} is not set, so Grok did not tag the {len(pending)} call(s) waiting for it.")
        return 0
    print(f"Grok tagged {tag_calls(pending, grok_model(), 'grok')} of {len(pending)} call(s).")
    return 0


def refilter(dry_run: bool = False) -> int:
    """`--refilter`: every portal's stored calls through the keyword filter again, after its rules change, and a review
    of any call newly kept. A dry run counts what would change and writes nothing."""
    from ledger.queries import calls_where
    from portals.shared.keyword_filter import decide, load_keywords

    _console_logging()
    total_dropped, total_kept = 0, 0
    for portal in registry.discover():
        if portal.keywords is None:
            continue
        stored = calls_where(portal=portal.name)
        was = {row["id"]: row["filter_result"] for row in stored}
        if dry_run:
            keywords = load_keywords(portal.keywords)
            now = {row["id"]: decide(row, keywords).result for row in stored}
        else:
            if stored:
                portal.filter(stored)
            now = {row["id"]: row["filter_result"] for row in calls_where(portal=portal.name)}
        dropped = [call_id for call_id, result in now.items() if result != "kept" and was.get(call_id) == "kept"]
        kept = [call_id for call_id, result in now.items() if result == "kept" and was.get(call_id) != "kept"]
        total_dropped += len(dropped)
        total_kept += len(kept)
        if dropped or kept:
            print(f"{portal.name}: {len(dropped)} newly dropped, {len(kept)} newly kept.")
        if kept and not dry_run:
            run_review(portal, None, no_review=False)
    print(f"{'Would drop' if dry_run else 'Dropped'} {total_dropped} and {'would keep' if dry_run else 'kept'} {total_kept} more call(s).")
    return 0


def load_fit_ratings(folder: str) -> int:
    """`--load-fit-ratings FOLDER`: take the team's ratings from the Call Fit Ratings page, exported as one JSON file a
    row. They live in the ledger and never in the repo, which is public. Run --fit-scores afterwards."""
    from ledger.queries import save_fit_ratings
    from review.fit import VALUES

    loaded = []
    for path in sorted(Path(folder).glob("*.json")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        row = doc.get("data", doc)
        if not row.get("rating"):   # a note with no rating yet
            continue
        if row["rating"] not in VALUES:
            raise ValueError(f"{path.name}: '{row['rating']}' is not a rating.")
        loaded.append(row)
    save_fit_ratings(loaded)
    print(f"Loaded {len(loaded)} fit rating(s).")
    return 0


def fit_scores(dry_run: bool = False) -> int:
    """`--fit-scores`: score every kept, reviewed call a judge has named the main work of, from the team's ratings.
    Run it after the ratings change. A dry run counts the bands and writes nothing."""
    from review.fit import band_line, score_all

    _console_logging()
    bands, looked_at = score_all(write=not dry_run)
    if bands is None:
        print("No fit ratings in the ledger yet: run --load-fit-ratings first.")
        return 0
    print(f"{'Would score' if dry_run else 'Scored'} {sum(bands.values())} of {looked_at} call(s): " + band_line(bands) + ".")
    return 0


def score_fit(rows: list[dict[str, Any]], write: bool = True) -> dict[str, int] | None:
    """Score these calls and store it; how many fell in each band, or None when nobody has rated anything yet."""
    from review.fit import score_rows

    return score_rows(rows, write)


# Rough answer sizes for the price of a re-judgment: thinking and the answer for Claude, reasoning and the answer for Grok.
REJUDGE_TOKENS_OUT = {"claude": 700, "grok": 1500}


def rejudge_open(dry_run: bool = False) -> int:
    """`--rejudge-open`: both judges rate every open, undecided call again with today's profile and name its main work,
    then the calls are scored. A dry run counts the calls and prices the run. Safe to rerun: a call a judge has already
    named the main work of is not asked again. Takes no lock, like the backfills."""
    from assistant.tools import open_undecided
    from drafting.costs import PRICES
    from ledger.queries import calls_where, main_work_by_call
    from review.feedback import build_examples_block
    from review.reviewer import GROK_MODEL_ID, MODEL_ID, build_prompt, review_calls

    _console_logging()
    rows = [row for row, _ in open_undecided(calls_where(filter_result="kept", reviewed=True), datetime.now(timezone.utc))]
    named = main_work_by_call()
    for_claude = [row for row in rows if not named.get(row["id"], {}).get("claude")]
    for_grok = [row for row in rows if not named.get(row["id"], {}).get("grok")] if grok_enabled() else []
    examples = build_examples_block()
    if dry_run:
        cost = 0.0
        for judge, model_id, pending in (("claude", MODEL_ID, for_claude), ("grok", GROK_MODEL_ID, for_grok)):
            price = PRICES[model_id]
            tokens_in = sum(len(build_prompt(row, "", examples)) // 4 for row in pending)
            cost += (tokens_in * price.input + len(pending) * REJUDGE_TOKENS_OUT[judge] * price.output) / 1_000_000
        print(f"{len(for_claude)} open calls for Claude, {len(for_grok)} for Grok; about ${cost:.2f}.")
        return 0
    if for_claude:
        review_calls(for_claude, review_model(), feedback_examples_block=examples)
    if for_grok:
        second_judge(for_grok, examples)
    named = main_work_by_call()
    done_claude = sum(1 for row in for_claude if named.get(row["id"], {}).get("claude"))
    done_grok = sum(1 for row in for_grok if named.get(row["id"], {}).get("grok"))
    print(f"Claude judged {done_claude} of {len(for_claude)} call(s); Grok judged {done_grok} of {len(for_grok)}.")
    bands = score_fit(rows)
    if bands:
        from review.fit import band_line

        print("Scored: " + band_line(bands) + ".")
    return 0


def workspace_notices(morning: bool = False) -> int:
    """The proposal workspace's notices in Slack (PW18): every few minutes, cards and steps ready; at 08:00, steps
    behind target and the digest. Nothing posts until WORKSPACE_SLACK is on. They never take the pipeline's lock."""
    from slack import workspace

    _console_logging()
    done = workspace.morning() if morning else workspace.announce()
    if done.get("off"):
        print("Workspace notices in Slack are off; set WORKSPACE_SLACK=on in .env to turn them on.")
    else:
        print("Workspace notices in Slack: " + ", ".join(f"{n} {kind}" for kind, n in done.items()))
    return 0


SUMMARY_TOKENS_OUT = 400   # the summary line, and the thinking the model does before it


def backfill_summaries(dry_run: bool = False) -> int:
    """Have Claude write the executive summary (phase 9c) for every call that has none, asking for the summary alone:
    the keyword filter's rejects and decided calls too, since All calls and Home show them. A dry run counts the calls
    and prices the run instead. Safe to rerun: a call that could not be summarized is asked again next time."""
    from drafting.costs import PRICES
    from ledger.queries import calls_without_summary
    from review.reviewer import MODEL_ID, build_summary_prompt, summarize_calls

    _console_logging()
    pending = calls_without_summary()
    if dry_run or not pending:
        price = PRICES[MODEL_ID]
        tokens_in = sum(len(build_summary_prompt(row)) // 4 for row in pending)
        cost = (tokens_in * price.input + len(pending) * SUMMARY_TOKENS_OUT * price.output) / 1_000_000
        print(f"{len(pending)} {'call needs' if len(pending) == 1 else 'calls need'} a summary; "
              f"about ${cost:.2f} with {MODEL_ID}.")
        return 0
    print(f"Summarized {summarize_calls(pending, review_model())} of {len(pending)} "
          f"{'call' if len(pending) == 1 else 'calls'}.")
    return 0


def backfill_judgments() -> int:
    """Copy the Claude review's existing verdicts into judgments, then have Grok judge every kept,
    reviewed call it has not judged yet. Safe to rerun: each pass only fills what is missing."""
    from ledger.queries import add_judgment, calls_without_judgment
    from review.feedback import build_examples_block
    from review.reviewer import MODEL_ID, is_judgment

    _console_logging()
    copied = 0
    for row in calls_without_judgment("claude"):
        reason = row.get("ai_reasoning") or ""
        if is_judgment(reason) and reason != NO_REVIEW_REASON:
            add_judgment(row["id"], "claude", MODEL_ID, row["ai_verdict"], reason, rated_at=row.get("reviewed_at"))
            copied += 1
    print(f"Copied {copied} Claude verdict(s) into judgments.")
    pending = calls_without_judgment("grok")
    if not grok_enabled():
        print(f"{GROK_KEY} is not set, so Grok did not judge the {len(pending)} call(s) waiting for it.")
        return 0
    judged = second_judge(pending, build_examples_block())
    print(f"Grok judged {judged} of {len(pending)} call(s).")
    return 0


def run_summary(portal: str, fresh: list[dict[str, Any]], counts: dict[str, Any], elapsed: float) -> dict[str, Any]:
    """The run's one line for Slack: calls scanned, and the new ones by verdict."""
    return {
        "portal": portal,
        "scanned": counts.get("fetched", 0),
        "new": len(fresh),
        "yes": sum(1 for r in fresh if r.get("ai_verdict") == "yes"),
        "maybe": sum(1 for r in fresh if r.get("ai_verdict") == "maybe"),
        "elapsed": elapsed,
    }


def deliver(portal: Portal, fresh: list[dict[str, Any]], counts: dict[str, int], elapsed: float, dry_run: bool) -> bool:
    """Post the run's summary to Slack, or print it in dry-run; True once posted. Since 4 Nov no card goes out per call
    (David): the new calls wait on the dashboard, where they are decided."""
    from slack.sink import post_run_summary, summary_text

    summary = run_summary(portal.name, fresh, counts, elapsed)
    if dry_run:
        print("\n===== DRY RUN: would post this summary to Slack =====")
        print(summary_text(summary))
        return False
    return post_run_summary(summary) is not None


def _run_seconds(run: dict[str, Any]) -> float:
    try:
        started, finished = (datetime.fromisoformat(str(run[k]).replace("Z", "+00:00")) for k in ("started_at", "finished_at"))
    except (KeyError, TypeError, ValueError):
        return 0.0
    return max(0.0, (finished - started).total_seconds())


def redeliver(run_id: int) -> int:
    """`--deliver-run N`: post run N's summary, held by --hold-slack or lost to a Slack failure."""
    from slack.sink import post_run_summary

    run = get_run(run_id)
    if run is None:
        print(f"no run {run_id}")
        return 2
    counts = json.loads(run.get("stage_counts") or "{}")
    posted = post_run_summary(run_summary(run.get("portal") or "Pipeline", new_calls(run_id), counts, _run_seconds(run)))
    print(f"deliver-run {run_id}: summary {'posted' if posted else 'not posted'}")
    return 0 if posted else 1


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


def write_brief(portals: list[Portal], now: datetime | None = None) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Store this week's Monday brief for the dashboard: each portal's week with its scraper line, and
    the Top 10 across portals with the top 10 umbrellas and announcements to watch. Returns (summaries, health, judges),
    so the Slack post shows the same."""
    from assistant.tools import RANKING, scraper_health, top_calls, top_watch, weekly_summary

    moment = now or datetime.now(timezone.utc)
    week_of = (moment.date() - timedelta(days=moment.weekday())).isoformat()
    summaries = [weekly_summary(p.slug, now=moment) for p in portals]
    health = [entry for p in portals for entry in scraper_health(p.slug, now=moment)["portals"]]
    judges = judge_records()
    scraper = {entry.get("name"): entry.get("text", "") for entry in health}
    for summary in summaries:
        save_brief(week_of, summary["portal"], {**summary, "health": scraper.get(summary["portal"], "")}, BRIEF_AUTHOR)
    save_brief(week_of, None, {"top": top_calls(BRIEF_TOP, now=moment), "watch": top_watch(BRIEF_TOP, now=moment),
                               "ranked_by": RANKING, "judges": judges}, BRIEF_AUTHOR)
    return summaries, health, judges


def store_brief() -> int:
    """`--write-brief`: this week's brief for the dashboard, with no Slack post."""
    _console_logging()
    portals = registry.discover()
    if not portals:
        print("No portals registered; nothing to store.")
        return 0
    summaries, _, _ = write_brief(portals)
    print(f"Stored this week's brief: {len(summaries)} portal(s) and the Top {BRIEF_TOP} across portals.")
    return 0


def post_summary() -> int:
    """Post the Monday summary, every portal's week and scraper health, as one Slack message, after
    storing the same week as the dashboard's Monday brief."""
    from slack.sink import post_text, weekly_summary_message

    _console_logging()
    portals = registry.discover()
    if not portals:
        print("No portals registered; nothing to post.")
        return 0
    summaries, health, judges = write_brief(portals)
    text, blocks = weekly_summary_message(summaries, health, judges=judges)
    ts = post_text(text, blocks=blocks)
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
    examples = build_examples_block()
    context = str(_payload(req).get("context") or "")
    passed, dropped = review_calls([row], review_model(), feedback_examples_block=examples, extra_context=context)
    second_judge([row], examples, extra_context=context)
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

        try:
            log.info("TAGS: rules tagged %d call(s)", tag_by_rules(run_id))
        except Exception as exc:   # tags are a convenience: never let them stop a scan
            log.warning("TAGS: rules skipped (%s: %s)", type(exc).__name__, str(exc)[:120])

        t0 = time.time()
        counts["reviewed"] = run_review(portal, args.limit, args.no_review)
        log.info("REVIEW: %d rows (%.1fs)", counts["reviewed"], time.time() - t0)

        try:
            log.info("SUMMARIES: %d call(s) summarized", run_summaries(portal, args.no_review))
        except Exception as exc:   # summaries are a convenience: never let them stop a scan
            log.warning("SUMMARIES: skipped (%s: %s)", type(exc).__name__, str(exc)[:120])

        try:
            log.info("FIT: %s", score_fit(calls_in_run(run_id)))
        except Exception as exc:   # the score is a convenience: never let it stop a scan
            log.warning("FIT: skipped (%s: %s)", type(exc).__name__, str(exc)[:120])

        fresh = new_calls(run_id)
        counts["new"] = len(fresh)
        log.info("NEW: %d rows", counts["new"])
        print_digest(portal.name, fresh)

        t0 = time.time()
        if args.hold_slack:
            print(f"Slack held: the summary waits for run.py --deliver-run {run_id}")
            posted = False
        else:
            posted = deliver(portal, fresh, counts, time.time() - started, args.dry_run)
        log.info("DELIVER: summary %s (%.1fs)", "posted" if posted else "not posted", time.time() - t0)
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

def linear_sync() -> int:
    """`--linear-sync`: an issue in Linear's Pursuits project for each call the team pursues, moved as the call moves
    (linear/pursuits.py). At 08:07 and 13:07, without the pipeline's lock; nothing happens without BD_LINEAR_API_KEY."""
    from linear.board import LinearBoard
    from linear.client import LinearClient
    from linear.pursuits import sync

    client = LinearClient()
    if not client.key:
        print("BD_LINEAR_API_KEY is not set: nothing synced to Linear (docs/RUNBOOK.md, Linear's Pursuits project).")
        return 0
    changes = sync(LinearBoard(client))
    for line in changes:
        print(line)
    print(f"linear-sync: {len(changes)} change(s)")
    return 0


# ------------------------------------------------------------------------- Ask Grok (David, 7 Nov 2026)

ASSISTANT = "assistant"                       # its row in workers, beside the Writer's worker
ASSISTANT_LOCK = DATA_DIR / "assistant.lock"
ASSISTANT_LOG_DIR = DATA_DIR / "assistant" / "logs"
ASSISTANT_POLL_S = 2.0                        # how often it looks for a question
ASSISTANT_BEAT_S = 30.0                       # how often it says it is alive while idle
ASSISTANT_DAILY_USD = 5.0                     # the team's daily budget, unless ASSISTANT_DAILY_USD says otherwise
FACTS_SHOWN = 40                              # the most Company Reference items one facts lookup hands over
FACT_SOURCES = {"facts": "00 Company Facts", "past_performance": "01 Past Performance Register",
                "products": "02 Products & Capabilities", "people": "03 People"}


def company_facts_tool() -> Any:
    """The company_facts tool for Ask Grok: Velocity's facts read live from 01 Company Reference (drafting/facts.py, which
    leaves out former employees), never an item marked SENSITIVE, with each open conflict marked. run.py supplies it so
    the assistant never imports the Writer's code."""
    from assistant.tools import Tool, _schema

    def company_facts(query: str = "", source: str = "") -> dict[str, Any]:
        import re

        from drafting.facts import load
        from drafting.steps import fix_dashes

        facts = load()
        words = [w for w in re.findall(r"[a-z0-9]+", query.lower()) if len(w) > 1]
        title = FACT_SOURCES.get(source)
        hoverslam = "hoverslam" in words
        scored = []
        for item in facts.items.values():
            if item.sensitive or (title and item.source != title):
                continue
            if "hoverslam" in item.entity.lower() and not hoverslam:
                continue
            text = f"{item.id} {item.text}".lower()
            hits = sum(1 for w in words if w in text)
            if words and not hits:
                continue
            scored.append((-hits, item))
        scored.sort(key=lambda pair: pair[0])
        shown = [item for _, item in scored[:FACTS_SHOWN]]
        lines = [f"{len(scored)} Velocity fact(s) match" + (f" '{query}'" if query else "")
                 + f", read from 01 Company Reference at {facts.read_at:%Y-%m-%d %H:%M} UTC" + (f" ({facts.note})" if facts.note else "")
                 + (f"; the {len(shown)} best:" if len(scored) > len(shown) else ":")]
        lines += [f"{item.id}{''.join(f' [{m}]' for m in facts.marks(item))} ({item.source}) | {item.text}" for item in shown]
        return {"ids": [item.id for item in shown], "total": len(scored), "text": fix_dashes("\n".join(lines))}

    return Tool("company_facts", "Velocity's own facts from 01 Company Reference, read live: registration, size and status, "
                "products and capabilities, people and their roles, past performance and its customers. Each has an id to "
                "cite. SENSITIVE items are never included.", "read",
                _schema({"query": {"type": "string", "description": "Words to look for, for example 'INDOPACOM' or 'WOSB'."},
                         "source": {"type": "string", "enum": list(FACT_SOURCES)}}),
                company_facts)


def assistant_tools() -> list[Any]:
    """Every read tool Ask Grok may call: the assistant's toolbox, then company_facts. No propose tool: answer only."""
    from assistant.tools import all_tools

    return [t for t in all_tools() if t.permission == "read"] + [company_facts_tool()]


def daily_budget() -> float:
    try:
        return float(config.get("ASSISTANT_DAILY_USD") or ASSISTANT_DAILY_USD)
    except ValueError:
        return ASSISTANT_DAILY_USD


def answer_cost(reply: Any, model: str) -> float:
    from drafting.costs import cost_of
    from drafting.llm import Usage

    return cost_of(Usage(phase_label="ask grok", model=model, input_tokens=reply.input_tokens, output_tokens=reply.output_tokens,
                         cache_read_tokens=reply.cached_tokens, cache_write_tokens=0, seconds=0.0, truncated=False, request_id=""))


def answer_question(row: dict[str, Any], model: Any, tools: list[Any]) -> str:
    """Answer one waiting question and store the answer, or why there is none; the state it ended in."""
    from assistant import chat
    from assistant.grok import MODEL_ID
    from ledger.queries import assistant_spend_today, finish_question, thread_history

    budget = daily_budget()
    if assistant_spend_today() >= budget:
        finish_question(row["id"], "failed", f"Ask Grok has used today's budget of ${budget:.2f}. It starts again at midnight UTC.")
        return "failed"
    history = [(h["question"], h["answer"]) for h in thread_history(row["thread_id"], row["asked_by"], row["id"])]
    name = getattr(model, "model", MODEL_ID)
    try:
        reply = chat.answer(row["question"], history, row.get("page"), model, tools, asked_by=row["asked_by"])
    except Exception as exc:   # Grok down or refusing: say so and keep serving
        log.warning("Question %s: Grok could not answer: %s: %s", row["id"], type(exc).__name__, str(exc)[:200])
        finish_question(row["id"], "failed", "Grok could not answer just now. Try again in a minute.", model=name)
        return "failed"
    cost = answer_cost(reply, name)
    finish_question(row["id"], "done", reply.text, sources=reply.sources, tools=reply.trace, model=name, cost_usd=cost)
    log.info("Question %s answered for %s: %d round(s), %d tool call(s), $%.4f", row["id"], row["asked_by"], reply.rounds,
             len(reply.trace), cost)
    return "done"


def draft_suggestion(call_id: str) -> tuple[dict[str, Any], float]:
    """Start the draft's suggestion for one call, from the Writer's model (drafting/suggest.py), and its cost."""
    from drafting.suggest import suggest

    return suggest(call_id)


def answer_suggestion(row: dict[str, Any]) -> str:
    """Make one waiting draft suggestion and store it, or why there is none; the state it ended in."""
    from drafting.llm import writer_model
    from ledger.queries import assistant_spend_today, finish_suggestion

    budget = daily_budget()
    if assistant_spend_today() >= budget:
        finish_suggestion(row["id"], "failed", note=f"Today's budget of ${budget:.2f} for Ask Grok and suggestions is used. "
                                                    "It starts again at midnight UTC.")
        return "failed"
    model = writer_model()
    try:
        suggestion, cost = draft_suggestion(row["call_id"])
    except Exception as exc:   # Claude down, the facts unreadable, an answer that could not be read
        log.warning("Suggestion %s for %s failed: %s: %s", row["id"], row["call_id"], type(exc).__name__, str(exc)[:200])
        finish_suggestion(row["id"], "failed", note="Claude could not make a suggestion just now. Try again in a minute.",
                          model=model)
        return "failed"
    finish_suggestion(row["id"], "done", suggestion, model=model, cost_usd=cost)
    log.info("Suggestion %s for %s made: $%.4f", row["id"], row["call_id"], cost)
    return "done"


def run_assistant(model: Any = None, max_questions: int | None = None, poll_s: float = ASSISTANT_POLL_S) -> int:
    """`--assistant`: answer Ask Grok's questions and make Start the draft's suggestions as they arrive, until stopped.
    With max_questions (tests), stop after that many, or as soon as none is waiting."""
    from assistant.grok import GrokChat
    from ledger.queries import claim_next_question, claim_next_suggestion, requeue_working_questions, worker_beat, worker_started

    model = model or GrokChat()
    tools = assistant_tools()
    worker_started(ASSISTANT)
    again = requeue_working_questions()
    if again:
        log.info("%d question(s) left half answered wait again", again)
    handled, beat = 0, time.monotonic()
    try:
        while max_questions is None or handled < max_questions:
            row = claim_next_question()
            if row is None:
                wanted = claim_next_suggestion()
                if wanted is not None:
                    worker_beat(ASSISTANT, "working", f"suggesting for {wanted['call_id']}")
                    answer_suggestion(wanted)
                    handled += 1
                    worker_beat(ASSISTANT, "idle")
                    beat = time.monotonic()
                    continue
                if max_questions is not None:
                    break
                if time.monotonic() - beat >= ASSISTANT_BEAT_S:
                    worker_beat(ASSISTANT, "idle")
                    beat = time.monotonic()
                time.sleep(poll_s)
                continue
            worker_beat(ASSISTANT, "working", f"answering question {row['id']}")
            answer_question(row, model, tools)
            handled += 1
            worker_beat(ASSISTANT, "idle")
            beat = time.monotonic()
    finally:
        worker_beat(ASSISTANT, "stopped")
    return 0


def serve_assistant() -> int:
    """The scheduled task's entry: one assistant at a time, logging to data/assistant/logs."""
    try:
        acquire_lock(ASSISTANT_LOCK)
    except LockHeld as exc:
        print(exc)
        return 0
    try:
        log_path = setup_logging(ASSISTANT_LOG_DIR)
        log.info("Ask Grok's assistant start; log %s; BD_XAI_API_KEY present: %s", log_path,
                 "yes" if config.get("BD_XAI_API_KEY") else "no")
        return run_assistant()
    finally:
        release_lock(ASSISTANT_LOCK)


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
    parser.add_argument("--deliver-run", type=int, metavar="N", help="post run N's Slack summary (held, or lost to a Slack failure), then exit")
    parser.add_argument("--hold-slack", action="store_true",
                        help="judge and save as usual but post no summary; run.py --deliver-run N posts it later")
    parser.add_argument("--wait-lock", type=int, default=0, metavar="MINUTES",
                        help="if another run holds the lock, wait up to this many minutes for it")
    parser.add_argument("--remind", action="store_true", help="post Slack reminders for Pursue calls due soon, then exit")
    parser.add_argument("--post-summary", action="store_true", help="post the weekly summary to Slack, then exit")
    parser.add_argument("--write-brief", action="store_true",
                        help="store this week's Monday brief for the dashboard without posting to Slack, then exit")
    parser.add_argument("--apply-requests", action="store_true",
                        help="carry out change requests approved on the dashboard, then exit")
    parser.add_argument("--backfill-judgments", action="store_true",
                        help="record Claude's past verdicts as judgments and have Grok judge the backlog, then exit")
    parser.add_argument("--backfill-tags", action="store_true",
                        help="tag every stored call by its rules and have Claude and Grok tag the reviewed ones, then exit")
    parser.add_argument("--workspace-slack", action="store_true",
                        help="post workspace notices to Slack: cards for pursued calls without one, steps ready; then exit")
    parser.add_argument("--workspace-morning", action="store_true",
                        help="post the morning's workspace notices to Slack: steps behind target, the digest per owner; then exit")
    parser.add_argument("--linear-sync", action="store_true",
                        help="open and move issues in Linear's Pursuits project to match the pursued calls, then exit")
    parser.add_argument("--refilter", action="store_true",
                        help="filter every stored call again with today's keywords, then exit; with --dry-run, count only")
    parser.add_argument("--load-fit-ratings", metavar="FOLDER",
                        help="take the team's fit ratings from the page's export, one JSON file a row, then exit")
    parser.add_argument("--fit-scores", action="store_true",
                        help="score every call a judge has named the main work of, then exit; with --dry-run, count only")
    parser.add_argument("--rejudge-open", action="store_true",
                        help="both judges rate every open, undecided call again and name its main work, then exit; "
                             "with --dry-run, count and price it")
    parser.add_argument("--backfill-summaries", action="store_true",
                        help="have Claude summarize each open, reviewed call that has no summary, then exit; "
                             "with --dry-run, count the calls and price the run instead")
    parser.add_argument("--assistant", action="store_true",
                        help="answer Ask Grok's questions from the dashboard as they arrive, until stopped")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if args.assistant:
        return serve_assistant()
    if args.remind:
        return remind()
    if args.post_summary:
        return post_summary()
    if args.write_brief:
        return store_brief()
    if args.apply_requests:
        return apply_requests(wait_s=args.wait_lock * 60)
    if args.backfill_judgments:
        return backfill_judgments()
    if args.backfill_tags:
        return backfill_tags()
    if args.backfill_summaries:
        return backfill_summaries(dry_run=args.dry_run)
    if args.refilter:
        return refilter(dry_run=args.dry_run)
    if args.load_fit_ratings:
        return load_fit_ratings(args.load_fit_ratings)
    if args.fit_scores:
        return fit_scores(dry_run=args.dry_run)
    if args.rejudge_open:
        return rejudge_open(dry_run=args.dry_run)
    if args.workspace_slack or args.workspace_morning:
        return workspace_notices(morning=args.workspace_morning)
    if args.linear_sync:
        return linear_sync()
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
