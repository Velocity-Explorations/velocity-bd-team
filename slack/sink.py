"""Slack informs; the dashboard decides (docs/DASHBOARD.md).

    ts = post_call(row)                  # one Block Kit card per new call, then set_slack()
    post_run_summary(summary)            # one line per run, pointing to the dashboard
    changes = collect_feedback()         # thread replies into notes; cards show decisions

Reactions on cards are not read: decisions are recorded on the dashboard. Every human reply
in a card's thread is appended to the call's human_notes (a leading "note:" is stripped);
the thread exists only for that call, so all of it is context. Each poll also edits any card
whose decision differs from the ledger, so the channel shows what was decided, by whom and
when. Undecided cards and the 50 most recently decided ones are polled. Cards the old
X-reaction flow deleted (dismissed by a Slack user id) are skipped.

Every Slack call has a 15 s timeout, honours Retry-After on 429, logs failures and never
raises into the pipeline. The token is never logged.
"""
from __future__ import annotations

import json
import logging
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from typing import Any

from config import get
from ledger.db import now_iso
from ledger.queries import append_note, get_call, pending_feedback, recent_decisions, set_slack

log = logging.getLogger("slack.sink")

API = "https://slack.com/api/"
TIMEOUT_S = 15
PAUSE_S = 0.3
MAX_RETRY_AFTER_S = 60
RECENT_DECIDED_LIMIT = 50   # decided cards still polled for late notes and decision changes

NOTE_PREFIX = "note:"
BADGE = {"yes": "\U0001F7E2 yes", "maybe": "\U0001F7E1 maybe"}   # green and yellow circles
# human_status -> (emoji, label) for the decision line on a card
DECISION_LABELS = {
    "pursue": ("\U0001F44D", "Pursue"),
    "not_relevant": ("\U0001F44E", "Not relevant"),
    "submitted": ("✅", "Submitted"),
    "dismissed": ("❌", "Dismissed"),
}
DECISION_BLOCK_PREFIX = "decision:"
SLACK_USER_ID = re.compile(r"^[UW][A-Z0-9]{6,}$")
MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
DECIDED_SHOWN = 10   # decisions listed in the weekly summary; the rest are on the dashboard


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

def dashboard_url() -> str:
    """Where the dashboard is served (DASHBOARD_URL), or "" when it is not hosted yet."""
    return (get("DASHBOARD_URL") or "").strip().rstrip("/")


def card_blocks(row: dict[str, Any]) -> list[dict[str, Any]]:
    verdict = (row.get("ai_verdict") or "maybe").lower()
    title = (row.get("title") or "(untitled)").replace("<", "(").replace(">", ")")
    url = row.get("url") or ""
    header = f"{BADGE.get(verdict, verdict)}  <{url}|{title}>" if url else f"{BADGE.get(verdict, verdict)}  {title}"
    context = f"id: `{row.get('id')}`  |  {row.get('portal') or ''}"
    if dashboard_url():
        context += f"  |  <{dashboard_url()}|Decide on the dashboard>"
    return [
        {"type": "section", "text": {"type": "mrkdwn", "text": header}},
        {"type": "section", "fields": [
            {"type": "mrkdwn", "text": f"*Due*\n{row.get('due_date') or 'n/a'}"},
            {"type": "mrkdwn", "text": f"*Type*\n{row.get('type') or 'n/a'}"},
            {"type": "mrkdwn", "text": f"*Match tier*\n{row.get('match_tier') or 'n/a'}"},
        ]},
        {"type": "section", "text": {"type": "mrkdwn", "text": (row.get("ai_reasoning") or "(no reasoning)")[:2900]}},
        {"type": "context", "elements": [{"type": "mrkdwn", "text": context}]},
    ]


def decision_signature(row: dict[str, Any]) -> str | None:
    """block_id of the decision line this card should carry, or None when undecided."""
    status = row.get("human_status")
    if not status:
        return None
    return f"{DECISION_BLOCK_PREFIX}{status}:{row.get('human_at') or ''}"[:255]


def _who(by: str | None, slack: bool) -> str:
    if not by:
        return "someone"
    return f"<@{by}>" if slack and SLACK_USER_ID.match(by) else by


def _when(iso: str | None, slack: bool) -> str:
    try:
        moment = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return iso or ""
    plain = moment.astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    # Slack renders this in each reader's own time zone; the text after | is the fallback.
    return f"<!date^{int(moment.timestamp())}^{{date_short_pretty}} at {{time}}|{plain}>" if slack else plain


def decision_text(row: dict[str, Any], slack: bool = True) -> str:
    status = row.get("human_status") or ""
    emoji, label = DECISION_LABELS.get(status, ("", status))
    by, at = _who(row.get("human_by"), slack), _when(row.get("human_at"), slack)
    return f"{emoji} *Decision: {label}* by {by}, {at}".strip() if slack else f"Decision: {label} by {by}, {at}"


def render_card(row: dict[str, Any]) -> list[dict[str, Any]]:
    """The card as it should look now: the decision line first when there is one."""
    signature = decision_signature(row)
    if signature is None:
        return card_blocks(row)
    head = {"type": "section", "block_id": signature, "text": {"type": "mrkdwn", "text": decision_text(row)}}
    return [head, *card_blocks(row)]


def card_fallback_text(row: dict[str, Any]) -> str:
    """Notification text for a card; starts with the decision when there is one."""
    text = card_text(row)
    return f"{decision_text(row, slack=False)}\n{text}" if row.get("human_status") else text


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
        "text": card_fallback_text(row),
        "blocks": render_card(row),
        "unfurl_links": False,
    })
    if not payload:
        return None
    ts = str(payload.get("ts") or "")
    set_slack(row["id"], str(payload.get("channel") or channel), ts)
    log.info("Posted card for %s (ts %s)", row.get("id"), ts)
    return ts


def summary_text(summary: dict[str, Any]) -> str:
    where = f"<{dashboard_url()}|the dashboard>" if dashboard_url() else "the dashboard"
    return (
        f"*{summary.get('portal', 'Pipeline')} scan*: {summary.get('scanned', 0)} calls scanned, "
        f"{summary.get('new', 0)} new ({summary.get('yes', 0)} yes, {summary.get('maybe', 0)} maybe), "
        f"{summary.get('elapsed', 0):.0f}s. Decide on {where}; reply in a card's thread to add a note."
    )


def post_text(text: str, client: SlackClient | None = None, blocks: list[dict[str, Any]] | None = None) -> str | None:
    """Post a message to the team channel; with `blocks`, `text` is the notification fallback.
    Returns its ts, or None when it was not sent."""
    client = client or SlackClient()
    channel = channel_id()
    if not channel:
        log.warning("post_text skipped: SLACK_CHANNEL_ID missing")
        return None
    params: dict[str, Any] = {"channel": channel, "text": text, "unfurl_links": False}
    if blocks:
        params["blocks"] = blocks
    payload = client.call("chat.postMessage", params)
    return str(payload.get("ts")) if payload else None


def _esc(text: str) -> str:
    """Escape the three characters Slack's mrkdwn reads as markup."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _linked(title: str, url: str | None) -> str:
    return f"<{url}|{_esc(title)}>" if url else _esc(title)


def _section(text: str) -> dict[str, Any]:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:3000]}}


def _deadline_day(deadline: str | None) -> date | None:
    """The calendar day of a deadline as the portal wrote it: "27 OCT 2026 : 21:59 MDT" or "2026-10-27"."""
    text = (deadline or "").strip()
    match = re.match(r"(\d{1,2}) ([A-Za-z]{3}) (\d{4})", text)
    try:
        if match:
            day, month, year = match.groups()
            return date(int(year), MONTHS.index(month.title()) + 1, int(day))
        return date.fromisoformat(text[:10])
    except ValueError:
        return None


def _closes(deadline: str | None, days_left: int | None) -> str:
    """'closes Tue 27 Oct (7 days)', or the deadline as written when it cannot be read."""
    day = _deadline_day(deadline)
    if day is None:
        return f"closes {_esc(deadline)}" if deadline else ""
    year = f" {day.year}" if day.year != date.today().year else ""
    when = f"closes {WEEKDAYS[day.weekday()]} {day.day} {MONTHS[day.month - 1]}{year}"
    if days_left is None:
        return when
    left = "today" if days_left == 0 else f"{days_left} day{'' if days_left == 1 else 's'}"
    return f"{when} ({left})"


def _decider(by: str | None) -> str:
    """A person's name; decisions made with Slack reactions before 2026-10-17 hold a user id instead."""
    if not by:
        return "unknown"
    return "decided in Slack" if SLACK_USER_ID.match(by) else _esc(by)


def weekly_summary_message(summaries: list[dict[str, Any]], health: list[dict[str, Any]],
                           now: datetime | None = None) -> tuple[str, list[dict[str, Any]]]:
    """The Monday summary as Slack blocks, plus a one-line fallback for notifications.

    `summaries` are assistant weekly_summary() results, one per portal; `health` are the
    entries of scraper_health()["portals"].
    """
    today = (now or datetime.now(timezone.utc)).date()
    monday = today - timedelta(days=today.weekday())
    title = f"Weekly BD summary, week of {monday.day} {MONTHS[monday.month - 1]}"
    base = dashboard_url()
    queue = f"<{base}/?state=open|Open the review queue>" if base else "Decide on the dashboard's review queue."
    scraper = {entry.get("name"): entry.get("text", "") for entry in health}
    blocks: list[dict[str, Any]] = [{"type": "header", "text": {"type": "plain_text", "text": title}}]
    fallback: list[str] = []
    for i, s in enumerate(summaries):
        if i:
            blocks.append({"type": "divider"})
        name, new, waiting = s.get("portal") or "Portal", s["new"]["total"], s.get("waiting", 0)
        fallback.append(f"{name}: {new} new, {waiting} waiting for a decision")
        calls = "call" if waiting == 1 else "calls"
        blocks.append(_section(f"*{_esc(name)}*: {new} new this week, {waiting} open {calls} waiting for a decision. {queue}"))
        picks = s.get("top_picks") or []
        if picks:
            lines = ["*Top picks*, open and undecided, ranked by verdict, then deadline:"]
            for n, c in enumerate(picks, 1):
                closes = _closes(c.get("deadline"), c.get("days_left"))
                lines.append(f"{n}. {_linked(c['title'], c.get('url'))}: {c.get('verdict')}" + (f", {closes}" if closes else ""))
                if c.get("reason"):
                    lines.append(f"      _{_esc(c['reason'])}_")
            blocks.append(_section("\n".join(lines)))
        pursued = [c for c in s.get("closing_soon") or [] if c.get("status") == "pursue"]
        if pursued:
            lines = ["*Pursued, closing within 14 days*"]
            lines += [f"\u2022 {_linked(c['title'], c.get('url'))}, {_closes(c.get('deadline'), c.get('days_left'))}" for c in pursued]
            blocks.append(_section("\n".join(lines)))
        decided = s.get("decided") or []
        if decided:
            lines = ["*Decided this week*"]
            for d in decided[:DECIDED_SHOWN]:
                label = DECISION_LABELS.get(d.get("status") or "", ("", d.get("status") or ""))[1]
                lines.append(f"\u2022 {label}: {_linked(d['title'], d.get('url'))} ({_decider(d.get('by'))})")
            if len(decided) > DECIDED_SHOWN:
                lines.append(f"and {len(decided) - DECIDED_SHOWN} more on the dashboard")
            blocks.append(_section("\n".join(lines)))
        if scraper.get(name):
            blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": f"Scraper: {_esc(scraper[name])}"}]})
    return f"{title}. " + "; ".join(fallback) + ".", blocks


def post_run_summary(summary: dict[str, Any], client: SlackClient | None = None) -> str | None:
    client = client or SlackClient()
    channel = channel_id()
    if not channel:
        log.warning("post_run_summary skipped: SLACK_CHANNEL_ID missing")
        return None
    payload = client.call("chat.postMessage", {"channel": channel, "text": summary_text(summary)})
    return str(payload.get("ts")) if payload else None


# ------------------------------------------------------------------------ feedback

def _slack_ts_to_iso(ts: str) -> str:
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    except (TypeError, ValueError):
        return now_iso()


def _deleted_by_old_flow(row: dict[str, Any]) -> bool:
    """Before 2026-10-17 an X reaction dismissed the call (human_by = Slack id) and deleted the card."""
    return row.get("human_status") == "dismissed" and bool(SLACK_USER_ID.match(row.get("human_by") or ""))


def collect_feedback(client: SlackClient | None = None, sleep: Callable[[float], None] = time.sleep) -> list[dict[str, Any]]:
    """Collect thread notes and bring cards in line with the ledger's decisions. Never raises."""
    client = client or SlackClient()
    changes: list[dict[str, Any]] = []
    try:
        undecided = pending_feedback()
        seen = {r["id"] for r in undecided}
        decided = [r for r in recent_decisions(RECENT_DECIDED_LIMIT)
                   if r.get("slack_ts") and r["id"] not in seen and not _deleted_by_old_flow(r)]
    except Exception as exc:
        log.warning("collect_feedback: ledger read failed: %s: %s", type(exc).__name__, str(exc)[:200])
        return changes
    log.info("Feedback: %d undecided and %d decided card(s) checked for notes and card edits", len(undecided), len(decided))
    for row in undecided + decided:
        try:
            change = _collect_one(row, client, sleep)
        except Exception as exc:   # one bad card never stops the poll
            log.warning("Feedback for %s failed: %s: %s", row.get("id"), type(exc).__name__, str(exc)[:200])
            continue
        if change:
            changes.append(change)
    return changes


def _collect_one(row: dict[str, Any], client: SlackClient, sleep: Callable[[float], None]) -> dict[str, Any] | None:
    channel, ts = row.get("slack_channel") or channel_id(), row.get("slack_ts") or ""
    change: dict[str, Any] = {"id": row["id"], "title": row.get("title") or "", "notes": [], "card_updated": False}

    thread = client.call("conversations.replies", {"channel": channel, "ts": ts, "limit": 100}, post=False)
    sleep(PAUSE_S)
    if not thread:
        return None   # card unreadable this time: change nothing, try again next poll
    messages = thread.get("messages") or []
    current = get_call(row["id"]) or row

    existing = current.get("human_notes") or ""
    for message in messages:
        if str(message.get("ts")) == ts:
            continue   # the card itself
        if message.get("bot_id") or message.get("subtype"):
            continue   # the bot's own messages and join/edit system notices
        text = (message.get("text") or "").strip()
        note = text[len(NOTE_PREFIX):].strip() if text.lower().startswith(NOTE_PREFIX) else text
        if not note or note in existing:
            continue
        existing = append_note(row["id"], note, by=str(message.get("user") or "?"), at=_slack_ts_to_iso(str(message.get("ts"))))
        change["notes"].append(note)
        log.info("Feedback: note on %s: %s", row["id"], note[:80])

    card = next((m for m in messages if str(m.get("ts")) == ts), None)
    if card is not None:
        shown = next((str(b.get("block_id")) for b in card.get("blocks") or []
                      if str(b.get("block_id") or "").startswith(DECISION_BLOCK_PREFIX)), None)
        wanted = decision_signature(current)
        if shown != wanted:
            edited = client.call("chat.update", {
                "channel": channel, "ts": ts, "text": card_fallback_text(current), "blocks": render_card(current),
            })
            sleep(PAUSE_S)
            if edited:
                change["card_updated"] = True
                log.info("Card for %s now shows: %s", row["id"], current.get("human_status") or "no decision")

    return change if (change["notes"] or change["card_updated"]) else None
