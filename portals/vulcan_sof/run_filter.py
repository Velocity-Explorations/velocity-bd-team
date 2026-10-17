"""Apply the keyword filter to Vulcan SOF calls in the ledger.

    python -m portals.vulcan_sof.run_filter          # rows still 'pending'
    python -m portals.vulcan_sof.run_filter --all    # every row, e.g. after editing keywords.yaml

Prints a summary and a table of every rejected title with its reason.
"""
from __future__ import annotations

import argparse
import sys

from ledger.queries import calls_where
from portals.shared.keyword_filter import REASON_NO_KEYWORD, Decision, filter_calls
from portals.vulcan_sof.portal import KEYWORDS_PATH
from portals.vulcan_sof.scrape import PORTAL


def summarize(kept: list[Decision], rejected: list[Decision]) -> dict[str, int]:
    return {
        "total": len(kept) + len(rejected),
        "kept_tight": sum(1 for d in kept if d.tier == "tight"),
        "kept_broad": sum(1 for d in kept if d.tier == "broad"),
        "rejected_blocklist": sum(1 for d in rejected if (d.reason or "").startswith("blocklist")),
        "rejected_no_keyword": sum(1 for d in rejected if d.reason == REASON_NO_KEYWORD),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Filter Vulcan SOF calls")
    parser.add_argument("--all", action="store_true", help="re-filter every row, not only pending ones")
    args = parser.parse_args(argv)

    rows = calls_where(portal=PORTAL, filter_result=None if args.all else "pending")
    kept, rejected = filter_calls(rows, KEYWORDS_PATH)
    s = summarize(kept, rejected)
    print(f"keywords: {KEYWORDS_PATH.name}")
    print(f"total={s['total']} kept-tight={s['kept_tight']} kept-broad={s['kept_broad']} "
          f"rejected-blocklist={s['rejected_blocklist']} rejected-no-keyword={s['rejected_no_keyword']}")
    if rejected:
        width = min(70, max(len(d.title) for d in rejected))
        print(f"\n{'rejected title':{width}s}  reason")
        for d in sorted(rejected, key=lambda d: d.title.lower()):
            print(f"{d.title[:width]:{width}s}  {d.reason}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
