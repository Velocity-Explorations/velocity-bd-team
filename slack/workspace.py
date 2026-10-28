"""Workspace notices in Slack (PW18, phase 10 of docs/design/redesign-plan.md).

    workspace.announce()          # every few minutes: cards for pursued calls without one, then steps ready
    workspace.morning()           # at 08:00: steps behind their target, then a digest per owner

A step ready for its owner, and a step behind its target date, are posted once each in the call's thread,
mentioning the owner by the Slack id DASHBOARD_USERS gives (`Name=<Slack id>`, comma separated). A pursued
call with no card gets one first, so its notices have a thread. Each morning every owner with steps waiting on
them (ready, failed, or past the budget) gets one digest in the channel. What was posted is kept as pursuit
events, so a notice goes out once; the digest's day is kept in data/slack/.

Nothing posts until WORKSPACE_SLACK is on: the team asked for fewer automatic posts in the channel (28 Oct).
"""
from __future__ import annotations

import json
import logging
import urllib.parse
from collections import defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from config import get
from ledger import queries as lq
from slack.sink import SLACK_USER_ID, SlackClient, channel_id, dashboard_url, post_call

log = logging.getLogger("slack.workspace")

DIGEST_FILE = Path(__file__).resolve().parent.parent / "data" / "slack" / "workspace_digest.txt"
STEP_NAMES = {
    "discovery": "Step 1, Discovery",
    "summary": "Step 2, Opportunity summary",
    "alignment": "Step 3, Alignment",
    "requirements": "Step 4, Requirements and checklist",
    "go_no_go": "The Go or no-go gate",
    "outline": "Step 5, Outline",
    "draft": "Step 6, First draft",
    "compliance": "Step 7, Compliance check",
    "reviews": "Step 8, Reviews",
    "final": "Step 9, Final checks",
    "submit": "The Submit gate",
}
WAITING_WORDS = {"ready": "ready for you", "failed": "failed: Retry it", "blocked": "budget reached: raise the cap"}


def enabled() -> bool:
    """Workspace posts are off until WORKSPACE_SLACK is on."""
    return (get("WORKSPACE_SLACK") or "").strip().lower() == "on"


def slack_ids() -> dict[str, str]:
    """Each person's Slack id from DASHBOARD_USERS (`Name=<Slack id>, ...`); names without one are left out."""
    found = {}
    for entry in (get("DASHBOARD_USERS") or "").split(","):
        name, _, slack_id = entry.partition("=")
        if SLACK_USER_ID.match(slack_id.strip()):
            found[name.strip()] = slack_id.strip()
    return found


def mention(name: str, ids: dict[str, str]) -> str:
    return f"<@{ids[name]}>" if name in ids else name


def step_name(step: str) -> str:
    return STEP_NAMES.get(step, step)


def workspace_link(call_id: str, step: str | None = None) -> str:
    """A link to the call's workspace at the step, or "" while the dashboard is not hosted."""
    if not dashboard_url():
        return ""
    query = f"?step={urllib.parse.quote(step)}" if step else ""
    return f"<{dashboard_url()}/proposals/{urllib.parse.quote(call_id, safe='')}{query}|Open the workspace>"


def _reply(client: Any, row: dict[str, Any], text: str) -> bool:
    payload = client.call("chat.postMessage", {"channel": row.get("slack_channel") or channel_id(), "thread_ts": row["slack_ts"],
                                               "text": text, "unfurl_links": False})
    return bool(payload)


def announce(client: Any = None) -> dict[str, Any]:
    """Cards for pursued calls without one, then each step newly ready for its owner, in the call's thread."""
    if not enabled():
        return {"off": True}
    client = client or SlackClient()
    cards = sum(1 for row in lq.pursued_calls_without_card() if post_call(row, client))
    ids = slack_ids()
    posted = 0
    for row in lq.steps_to_announce():
        if not lq.needs_owner(row["step"], row["approval_mode"]) or not row["slack_ts"]:
            continue   # the worker approves it itself, or the call's card could not be posted
        text = f"{mention(row['owner'], ids)} {step_name(row['step'])} is ready for you. {workspace_link(row['call_id'], row['step'])}"
        if _reply(client, row, text.strip()):
            lq.add_event(row["pursuit_id"], "slack", "slack_ready", f"Posted to Slack: {step_name(row['step'])} is ready", row["id"])
            posted += 1
    return {"cards": cards, "ready": posted}


def _behind(client: Any, today: date, ids: dict[str, str]) -> int:
    posted = 0
    for row in lq.steps_behind_target():
        try:
            target = json.loads(row["target_dates"] or "{}").get(row["step"])
        except ValueError:
            target = None
        if not target or target >= today.isoformat() or not row["slack_ts"]:
            continue
        text = (f"{mention(row['owner'], ids)} {step_name(row['step'])} is behind its target of {target}. "
                f"{workspace_link(row['call_id'], row['step'])}")
        if _reply(client, row, text.strip()):
            lq.add_event(row["pursuit_id"], "slack", "slack_behind", f"Posted to Slack: {step_name(row['step'])} is behind its target",
                         row["id"])
            posted += 1
    return posted


def _digests(client: Any, today: date, ids: dict[str, str]) -> int:
    """One message per owner with what waits on them, once a day."""
    if DIGEST_FILE.exists() and DIGEST_FILE.read_text(encoding="utf-8").strip() == today.isoformat():
        return 0
    waiting: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in lq.steps_waiting_on_owners():
        if row["state"] != "ready" or lq.needs_owner(row["step"], row["approval_mode"]):
            waiting[row["owner"]].append(row)
    posted = 0
    for owner, rows in waiting.items():
        head = f"{mention(owner, ids)} {len(rows)} {'step waits' if len(rows) == 1 else 'steps wait'} on you this morning:"
        lines = [f"• {r['title'] or r['call_id']}: {step_name(r['step'])}, {WAITING_WORDS[r['state']]}" for r in rows]
        link = f"<{dashboard_url()}/proposals?view=drafting|Proposals, Drafting>" if dashboard_url() else ""
        payload = client.call("chat.postMessage", {"channel": channel_id(), "text": "\n".join([head, *lines, link]).strip(),
                                                   "unfurl_links": False})
        posted += 1 if payload else 0
    DIGEST_FILE.parent.mkdir(parents=True, exist_ok=True)
    DIGEST_FILE.write_text(today.isoformat(), encoding="utf-8")
    return posted


def morning(client: Any = None, today: date | None = None) -> dict[str, Any]:
    """Steps behind their target, once each in the call's thread; then the digest per owner, once a day (PW18)."""
    if not enabled():
        return {"off": True}
    client = client or SlackClient()
    today = today or date.today()
    ids = slack_ids()
    return {"behind": _behind(client, today, ids), "digests": _digests(client, today, ids)}
