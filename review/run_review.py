"""Review the kept, unreviewed calls of a run with the LLM.

    python -m review.run_review                 # latest run
    python -m review.run_review --run-id 3 --limit 5
    python -m review.run_review --debug         # also logs the first rendered prompt

Prints title | match_tier | verdict | reason per row, totals per verdict, elapsed time.
"""
from __future__ import annotations

import argparse
import logging
import sys
import time

from config import ConfigError
from ledger.queries import calls_for_review, latest_run_id
from review.reviewer import AnthropicModel, review_calls

log = logging.getLogger("review.run")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="LLM review of filtered calls")
    parser.add_argument("--run-id", type=int, help="run to review (default: latest run)")
    parser.add_argument("--limit", type=int, help="review at most N rows")
    parser.add_argument("--debug", action="store_true", help="DEBUG logging, including the first prompt")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    for noisy in ("httpx2", "httpcore2", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    logging.getLogger("anthropic").setLevel(logging.WARNING)

    run_id = args.run_id or latest_run_id()
    if run_id is None:
        print("no runs in the ledger")
        return 1
    rows = calls_for_review(run_id)
    if args.limit:
        rows = rows[: args.limit]
    print(f"run {run_id}: {len(rows)} rows to review")
    if not rows:
        return 0

    try:
        model = AnthropicModel()
    except ConfigError as exc:
        print(exc)
        return 2

    started = time.time()
    passed, dropped = review_calls(rows, model)
    elapsed = time.time() - started

    everything = sorted(passed + dropped, key=lambda r: r.title.lower())
    width = min(60, max(len(r.title) for r in everything))
    print(f"\n{'title':{width}s} | tier  | verdict | reason")
    for r in everything:
        print(f"{r.title[:width]:{width}s} | {(r.match_tier or ''):5s} | {r.verdict:7s} | {r.reason}")
    counts = {v: sum(1 for r in everything if r.verdict == v) for v in ("yes", "maybe", "no")}
    print(f"\ntotals: yes={counts['yes']} maybe={counts['maybe']} no={counts['no']} (of {len(everything)})")
    print(f"elapsed: {elapsed:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
