"""Pipeline entry point (stub until Phase 1).

    python run.py --portal vulcan_sof --dry-run

Phase 1 adds the lock file, the portal dispatch, and the runs bookkeeping. Nothing here
scrapes yet.
"""
from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="velocity-bd-team pipeline")
    parser.add_argument("--portal", help="run a single portal by slug (e.g. vulcan_sof)")
    parser.add_argument("--dry-run", action="store_true", help="scrape and review but write nothing to the ledger")
    args = parser.parse_args(argv)
    print(f"run.py stub: portal={args.portal or 'all'} dry_run={args.dry_run}. Pipeline arrives in Phase 1.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
