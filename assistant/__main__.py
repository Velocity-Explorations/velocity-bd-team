"""Try the assistant's tools from the command line.

    python -m assistant tools                          # every tool and its permission
    python -m assistant profile vulcan_sof
    python -m assistant explain <call id>              # add --json for the full result
    python -m assistant brief <call id>
    python -m assistant deadlines [--days 14] [--portal vulcan_sof]
    python -m assistant health [--portal vulcan_sof]
    python -m assistant summary [--portal vulcan_sof] [--days 7]
    python -m assistant preview vulcan_sof --add-broad "digital twin" [--add-block "\\bturret\\b"]
    python -m assistant tuning vulcan_sof [--min-examples 3]

Change requests (approved on the dashboard, carried out by `python run.py --apply-requests`):

    python -m assistant propose keyword vulcan_sof --add-broad "digital twin" --reason "..." --by "David Wood"
    python -m assistant propose rereview <call id> --context "It is a software layer, not hardware."
    python -m assistant propose scan vulcan_sof
    python -m assistant propose draft <call id> [--notes "Lead with Echo C2."]
    python -m assistant propose fault vulcan_sof --description "Logins have failed twice this week."
    python -m assistant requests [--status proposed]

The scheduled Slack posts (deadline reminders, the weekly summary) run from run.py:
`python run.py --remind` and `python run.py --post-summary`.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from assistant import requests, tools
from assistant.tools import ToolError

DEADLINE_DAYS = 14


def _print(result: dict[str, Any], as_json: bool) -> None:
    print(json.dumps(result, indent=2, ensure_ascii=False, default=str) if as_json else result["text"])


def _change_args(parser: argparse.ArgumentParser) -> None:
    for name in tools.CHANGE_KEYS:
        flag = "--" + name.replace("_", "-")
        parser.add_argument(flag, dest=name, action="append", default=[], metavar="WORD",
                            help=f"{name.replace('_', ' ')} (repeatable)")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m assistant", description="The portal assistant's tools")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("tools", help="list every tool and its permission")
    for name, needs in (("profile", "portal"), ("explain", "call_id"), ("brief", "call_id")):
        p = sub.add_parser(name)
        p.add_argument(needs)
        p.add_argument("--json", action="store_true")
    p = sub.add_parser("deadlines")
    p.add_argument("--days", type=int, default=DEADLINE_DAYS)
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

    p = sub.add_parser("requests", help="change requests and where each stands")
    p.add_argument("--status", choices=requests.STATUSES)
    p.add_argument("--limit", type=int, default=20)
    p.add_argument("--json", action="store_true")

    propose = sub.add_parser("propose", help="record a change request for approval on the dashboard")
    kinds = propose.add_subparsers(dest="kind", required=True)
    k = kinds.add_parser("keyword", help="change a portal's keywords")
    k.add_argument("portal")
    _change_args(k)
    r = kinds.add_parser("rereview", help="review one call again with the team's context")
    r.add_argument("call_id")
    r.add_argument("--context", required=True)
    s = kinds.add_parser("scan", help="scan one portal now")
    s.add_argument("portal")
    d = kinds.add_parser("draft", help="start a response draft for one call")
    d.add_argument("call_id")
    d.add_argument("--notes", default="")
    f = kinds.add_parser("fault", help="report a scraper fault as a GitHub issue")
    f.add_argument("portal")
    f.add_argument("--description", required=True)
    for p in (k, r, s, d, f):
        if p is not f:
            p.add_argument("--reason", default="", help="why it is needed")
        p.add_argument("--by", default="command line", help="who is asking (default: command line)")
        p.add_argument("--json", action="store_true")
    return parser


def _propose(args: argparse.Namespace) -> dict[str, Any]:
    if args.kind == "keyword":
        return requests.propose_keyword_change(args.portal, reason=args.reason, requested_by=args.by,
                                               **{key: getattr(args, key) for key in tools.CHANGE_KEYS})
    if args.kind == "rereview":
        return requests.propose_rereview(args.call_id, args.context, reason=args.reason, requested_by=args.by)
    if args.kind == "scan":
        return requests.propose_scan(args.portal, reason=args.reason, requested_by=args.by)
    if args.kind == "draft":
        return requests.propose_draft(args.call_id, notes=args.notes, reason=args.reason, requested_by=args.by)
    return requests.propose_fault_report(args.portal, args.description, requested_by=args.by)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    args = build_parser().parse_args(argv)
    try:
        if args.command == "tools":
            for t in tools.all_tools():
                print(f"{t.name:24s} {t.permission:8s} {t.description}")
            return 0
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
        elif args.command == "tuning":
            result = tools.tuning_report(args.portal, min_examples=args.min_examples)
        elif args.command == "requests":
            result = requests.list_change_requests(status=args.status, limit=args.limit)
        else:
            result = _propose(args)
    except ToolError as exc:
        print(exc)
        return 2
    _print(result, getattr(args, "json", False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
