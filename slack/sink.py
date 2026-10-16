"""Slack delivery of new calls and collection of the team's reactions as feedback.

    ts = post_call(row)                  # one Block Kit card per new call, then set_slack()
    post_run_summary(summary)            # one line per run
    changes = collect_feedback()         # reactions and "note:" replies into the ledger

Reactions on a card:  +1 -> pursue, -1 -> not_relevant, white_check_mark -> submitted,
x -> dismissed (and the card is deleted). Priority when several are present: x, then
white_check_mark, then -1, then +1. A thread reply starting with "note:" is appended to
the call's human_notes. Cards already decided are still polled (the last 50): their notes
are collected, and an X placed later still dismisses; other reactions no longer change them.

Every Slack call has a 15 s timeout, honours Retry-After on 429, logs failures and never
raises into the pipeline. The token is never logged.
"""
from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from config import get
from ledger.db import now_iso
from ledger.queries import append_note, get_call, pending_feedback, recent_decisions, set_human, set_slack

log = logging.getLogger("slack.sink")

API = "https://slack.com/api/"
TIMEOUT_S = 15
PAUSE_S = 0.3
MAX_RETRY_AFTER_S = 60
RECENT_DECIDED_LIMIT = 50   # decided cards still polled for late notes and a later X

# reaction name -> human_status, in priority order (first match wins)
REACTION_STATUS: list[tuple[tuple[str, ...], str]] = [
    (("x",), "dismissed"),
    (("white_check_mark",), "submitted"),
    (("-1", "thumbsdown"), "not_relevant"),
    (("+1", "thumbsup"), "pursue"),
]
NOTE_PREFIX = "note:"
BADGE = {"yes": "\U0001F7E2 yes", "maybe": "\U0001F7E1 maybe"}   # green and yellow circles
SUMMARY_HINT = (
    "React \U0001F44D \U0001F44E ✅ ❌ on any card; reply 'note: ...' in its thread to explain."
)


class SlackClient:
    """Minimal Web API client on urllib. call() returns the parsed payload or None."""

    def __init__(self, token: str | None = None, sleep: Callable[[float], None] = time.sleep) -> None:
        self.token = token if token is not None else (get("BD_SLACK_BOT_TOKEN") or "")
        self.sleep = sleep

    def call(self, method: str, params: dict[str, Any], post: bool = True) -> dict[str, Any] | None:
        if not self.token:
            log.warning("Slack %s skipped: BD_SLACK_BOT_TOKEN missing", method)
            return None
        for attempt in (1, 2):
            try:
                request = self._request(method, params, post)
                with urllib.request.urlopen(request, timeout=TIMEOUT_S) as response:
                    payload = json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as exc:
                if exc.code == 429 and attempt == 1:
                    wait = min(int(exc.headers.get("Retry-After", "1") or 1), MAX_RETRY_AFTER_S)
                    log.warning("Slack %s rate limited; waiting %ds", method, wait)
                    self.sleep(wait)
                    continue
                log.warning("Slack %s failed: HTTP %s %s", method, exc.code, str(exc.reason)[:200])
                return None
            except (urllib.error.URLError, TimeoutError, ValueError, OSError) as exc:
                log.warning("Slack %s failed: %s: %s", method, type(exc).__name__, str(exc)[:200])
                return None
            if not payload.get("ok"):
                log.warning("Slack %s rejected: %s", method, str(payload.get("error", payload))[:200])
                return None
            return payload
        return None

    def _request(self, method: str, params: dict[str, Any], post: bool) -> urllib.request.Request:
        headers = {"Authorization": f"Bearer {self.token}"}
        if post:
            headers["Content-Type"] = "application/json; charset=utf-8"
            return urllib.request.Request(API + method, data=json.dumps(params).encode("utf-8"), headers=headers, method="POST")
        query = urllib.parse.urlencode({k: v for k, v in params.items() if v is not None})
        return urllib.request.Request(f"{API}{method}?{query}", headers=headers, method="GET")


def channel_id() -> str:
    return get("SLACK_CHANNEL_ID") or ""


# -------------------------------------------------------------------------- cards

def card_blocks(row: dict[str, Any]) -> list[dict[str, Any]]:
    verdict = (row.get("ai_verdict") or "maybe").lower()
    title = (row.get("title") or "(untitled)").replace("<", "(").replace(">", ")")
    url = row.get("url") or ""
    header = f"{BADGE.get(verdict, verdict)}  <{url}|{title}>" if url else f"{BADGE.get(verdict, verdict)}  {title}"
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Due*\n{row.get('due_date') or 'n/a'}"},
            {"type": "mrkdwn", "text": f"*Type*\n{row.get('type') or 'n/a'}"},
            {"type": "mrkdwn", "text": f"*Match tier*\n{row.get('match_tier') or 'n/a'}"},
        ]},
        {"type": "section", "text": {"type": "mrkdwn", "text": (row.get("ai_reasoning") or "(no reasoning)")[:2900]}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": f"id: `{row.get('id')}`  |  {row.get('portal') or ''}"}]},
    ]


def card_text(row: dict[str, Any]) -> str:
    """Plain rendering of a card, for --dry-run and for Slack's notification fallback."""
    verdict = (row.get("ai_verdict") or "maybe").upper()
    return (
        f"[{verdict}] {row.get('title') or '(untitled)'}\n"
        f"  Due: {row.get('due_date') or 'n/a'} | Type: {row.get('type') or 'n/a'} | Tier: {row.get('match_tier') or 'n/a'}\n"
        f"  {row.get('url') or ''}\n"
        f"  {row.get('ai_reasoning') or ''}\n"
        f"  id: {row.get('id')}"
    )


def post_call(row: dict[str, Any], client: SlackClient | None = None) -> str | None:
    client = client or SlackClient()
    channel = channel_id()
    if not channel:
        log.warning("post_call skipped: SLACK_CHANNEL_ID missing")
        return None
    payload = client.call("chat.postMessage", {
        "channel": channel,
        "text": card_text(row),
        "blocks": card_blocks(row),
        "unfurl_links": False,
    })
    if not payload:
        return None
    ts = str(payload.get("ts") or "")
    set_slack(row["id"], str(payload.get("channel") or channel), ts)
    log.info("Posted card for %s (ts %s)", row.get("id"), ts)
    return ts


def summary_text(summary: dict[str, Any]) -> str:
    return (
        f"*{summary.get('portal', 'Pipeline')} scan*: {summary.get('scanned', 0)} calls scanned, "
        f"{summary.get('new', 0)} new ({summary.get('yes', 0)} yes, {summary.get('maybe', 0)} maybe), "
        f"{summary.get('elapsed', 0):.0f}s. {SUMMARY_HINT}"
    )


def post_run_summary(summary: dict[str, Any], client: SlackClient | None = None) -> str | None:
    client = client or SlackClient()
    channel = channel_id()
    if not channel:
        log.warning("post_run_summary skipped: SLACK_CHANNEL_ID missing")
        return None
    payload = client.call("chat.postMessage", {"channel": channel, "text": summary_text(summary)})
    return str(payload.get("ts")) if payload else None


# ------------------------------------------------------------------------ feedback

def status_from_reactions(reactions: list[dict[str, Any]]) -> tuple[str, str] | None:
    """(human_status, user_id) for the highest-priority recognised reaction, else None."""
    by_name = {r.get("name", ""): r for r in reactions if r.get("name")}
    for names, status in REACTION_STATUS:
        for name in names:
            reaction = by_name.get(name)
            if reaction and reaction.get("users"):
                return status, str(reaction["users"][0])
    return None


def _slack_ts_to_iso(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return now_iso()


def collect_feedback(client: SlackClient | None = None, sleep: Callable[[float], None] = time.sleep) -> list[dict[str, Any]]:
    """Poll reactions and thread notes for every card awaiting a decision. Never raises."""
    client = client or SlackClient()
    changes: list[dict[str, Any]] = []
    try:
        pending = pending_feedback()
        # Cards decided recently still get polled: notes often arrive after the reaction,
        # and a later X should still dismiss. Only X can override an existing decision.
        pending_ids = {r["id"] for r in pending}
        decided = [r for r in recent_decisions(RECENT_DECIDED_LIMIT)
                   if r.get("slack_ts") and r["id"] not in pending_ids and r.get("human_status") != "dismissed"]   # dismissed cards are deleted
    except Exception as exc:
        log.warning("collect_feedback: ledger read failed: %s: %s", type(exc).__name__, str(exc)[:200])
        return changes
    log.info("Feedback: %d card(s) awaiting a decision, %d decided card(s) rechecked for notes", len(pending), len(decided))
    for row, is_pending in [(r, True) for r in pending] + [(r, False) for r in decided]:
        try:
            change = _collect_one(row, client, sleep, is_pending)
        except Exception as exc:   # one bad card never stops the poll
            log.warning("Feedback for %s failed: %s: %s", row.get("id"), type(exc).__name__, str(exc)[:200])
            continue
        if change:
            changes.append(change)
    return changes


def _collect_one(row: dict[str, Any], client: SlackClient, sleep: Callable[[float], None], pending: bool = True) -> dict[str, Any] | None:
    channel, ts = row.get("slack_channel") or channel_id(), row.get("slack_ts") or ""
    change: dict[str, Any] = {"id": row["id"], "title": row.get("title") or "", "status": None, "by": None, "notes": []}

    reactions = client.call("reactions.get", {"channel": channel, "timestamp": ts, "full": "true"}, post=False)
    sleep(PAUSE_S)
    if reactions:
        decision = status_from_reactions((reactions.get("message") or {}).get("reactions") or [])
        if decision and (pending or (decision[0] == "dismissed" and row.get("human_status") != "dismissed")):
            status, user = decision
            set_human(row["id"], status, user, now_iso())
            change["status"], change["by"] = status, user
            log.info("Feedback: %s -> %s by %s", row["id"], status, user)

    replies = client.call("conversations.replies", {"channel": channel, "ts": ts, "limit": 100}, post=False)
    sleep(PAUSE_S)
    if replies:
        existing = (get_call(row["id"]) or {}).get("human_notes") or ""
        for message in replies.get("messages") or []:
            if str(message.get("ts")) == ts:
                continue   # the card itself
            text = (message.get("text") or "").strip()
            if not text.lower().startswith(NOTE_PREFIX):
                continue
            note = text[len(NOTE_PREFIX):].strip()
            if not note or note in existing:
                continue
            existing = append_note(row["id"], note, by=str(message.get("user") or "?"), at=_slack_ts_to_iso(str(message.get("ts"))))
            change["notes"].append(note)
            log.info("Feedback: note on %s: %s", row["id"], note[:80])

    if change["status"] == "dismissed":
        if client.call("chat.delete", {"channel": channel, "ts": ts}):
            log.info("Deleted dismissed card %s", row["id"])
        sleep(PAUSE_S)

    return change if (change["status"] or change["notes"]) else None
