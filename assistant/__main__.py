"""Try the assistant's tools from the command line, and run its scheduled Slack jobs.

    python -m assistant tools                          # every tool and its permission
    python -m assistant profile vulcan_sof
    python -m assistant explain <call id>              # add --json for the full result
    python -m assistant brief <call id>
    python -m assistant deadlines [--days 14] [--portal vulcan_sof]
    python -m assistant health [--portal vulcan_sof]
    python -m assistant summary [--portal vulcan_sof] [--days 7]
    python -m assistant preview vulcan_sof --add-broad "digital twin" [--add-block "\\bturret\\b"]
    python -m assistant tuning vulcan_sof [--min-examples 3]

Scheduled jobs (docs/RUNBOOK.md):

    python -m assistant remind          # daily: post deadline reminders, nothing when none are due
    python -m assistant post-summary    # weekly: post each portal's summary and scraper health
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from assistant import tools
from assistant.tools import ToolError
from portals import registry
from slack.sink import post_text

REMIND_DAYS = 14


def _print(result: dict[str, Any], as_json: bool) -> None:
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str) if as_json else result["text"])


def _change_args(parser: argparse.ArgumentParser) -> None:
    for name in tools.CHANGE_KEYS:
        flag = "--" + name.replace("_", "-")
        parser.add_argument(flag, dest=name, action="append", default=[], metavar="WORD",
                            help=f"{name.replace('_', ' ')} (repeatable)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m assistant", description="The portal assistant's tools and jobs")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("tools", help="list every tool and its permission")
    for name, needs in (("profile", "portal"), ("explain", "call_id"), ("brief", "call_id")):
        p = sub.add_parser(name)
        p.add_argument(needs)
        p.add_argument("--json", action="store_true")
    p = sub.add_parser("deadlines")
    p.add_argument("--days", type=int, default=REMIND_DAYS)
    p.add_argument("--portal")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("health")
    p.add_argument("--portal")
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("summary")
    p.add_argument("--portal")
    p.add_argument("--days", type=int, default=7)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("preview")
    p.add_argument("portal")
    _change_args(p)
    p.add_argument("--json", action="store_true")
    p = sub.add_parser("tuning")
    p.add_argument("portal")
    p.add_argument("--min-examples", type=int, default=3)
    p.add_argument("--json", action="store_true")
    sub.add_parser("remind", help="post deadline reminders to Slack")
    sub.add_parser("post-summary", help="post the weekly summary to Slack")
    return parser


def remind() -> int:
    result = tools.upcoming_deadlines(days=REMIND_DAYS)
    if not result["calls"]:
        print("No Pursue deadlines in the next 14 days; nothing to post.")
        return 0
    ts = post_text("*Deadline reminder*\n" + result["text"])
    print(f"Posted {len(result['calls'])} reminder(s)" + ("" if ts else " (Slack did not accept the post; see the log)"))
    return 0 if ts else 1


def post_summary() -> int:
    parts = []
    for p in registry.discover():
        summary = tools.weekly_summary(p.slug)
        health = tools.scraper_health(p.slug)
        parts.append(f"{summary['text']}\nScraper: {health['text']}")
    if not parts:
        print("No portals registered; nothing to post.")
        return 0
    ts = post_text("\n\n".join(parts))
    print("Posted the weekly summary" + ("" if ts else " (Slack did not accept the post; see the log)"))
    return 0 if ts else 1


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "tools":
            for t in tools.TOOLS:
                print(f"{t.name:24s} {t.permission:8s} {t.description}")
            return 0
        if args.command == "remind":
            return remind()
        if args.command == "post-summary":
            return post_summary()
        if args.command == "profile":
            result = tools.portal_profile(args.portal)
        elif args.command == "explain":
            result = tools.explain_call(args.call_id)
        elif args.command == "brief":
            result = tools.brief_call(args.call_id)
        elif args.command == "deadlines":
            result = tools.upcoming_deadlines(days=args.days, portal=args.portal)
        elif args.command == "health":
            result = tools.scraper_health(portal=args.portal)
        elif args.command == "summary":
            result = tools.weekly_summary(portal=args.portal, days=args.days)
        elif args.command == "preview":
            result = tools.preview_keyword_change(args.portal, **{k: getattr(args, k) for k in tools.CHANGE_KEYS})
        else:
            result = tools.tuning_report(args.portal, min_examples=args.min_examples)
    except ToolError as exc:
        print(exc)
        return 2
    _print(result, getattr(args, "json", False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
