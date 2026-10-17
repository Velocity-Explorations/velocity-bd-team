"""Propose tools: record a change request for a person to approve (docs/ASSISTANT.md, "Approvals").

A propose tool checks the request, works out what it would do (the preview a person reads
before approving) and records it in the ledger's change_requests table. It changes nothing
else. A person approves or rejects it on the dashboard's Requests page, and
`python run.py --apply-requests` carries out approved requests, except drafts, which wait
for the Writer.

`requested_by` is filled in by whatever runs the tool (the Slack bot, the command line),
never by the model, so it is not among any tool's parameters.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from assistant.tools import (
    CALL_ARG,
    PORTAL_ARG,
    WORDS,
    Tool,
    ToolError,
    _get,
    _plural,
    _schema,
    _sentence,
    _when,
    brief_call,
    preview_keyword_change,
    resolve_portal,
    scraper_health,
)
from config import get
from ledger.queries import create_request, find_open_request, get_request, list_requests, recent_runs
from portals.shared.keyword_filter import describe_changes

STATUSES = ("proposed", "approved", "rejected", "applying", "applied", "failed")
TITLE_CHARS = 80
APPLY_EVERY = "15 minutes"   # how often the scan machine looks for approved requests (scripts/install-schedule.ps1)


def dashboard_link() -> str:
    """The dashboard's Requests page, or "" when DASHBOARD_URL is not set."""
    base = (get("DASHBOARD_URL") or "").strip().rstrip("/")
    return f"{base}/requests" if base else ""


def _portal_slug(name: str | None) -> str | None:
    try:
        return resolve_portal(name or "").slug
    except ToolError:
        return None


def _clean(text: str | None) -> str:
    return " ".join((text or "").split())


def _decode(text: str | None) -> Any:
    try:
        return json.loads(text) if text else None
    except ValueError:
        return None


def _status_phrase(req: dict[str, Any]) -> str:
    status = req["status"]
    if status == "proposed":
        return f"waiting for approval (asked by {req['requested_by']}, {_when(req['requested_at'])})"
    if status == "rejected":
        note = f": {req['decision_note']}" if req.get("decision_note") else ""
        return f"rejected by {req.get('decided_by') or 'someone'}{note}"
    if status == "approved":
        phrase = f"approved by {req.get('decided_by') or 'someone'}"
        if req["kind"] == "draft":
            return phrase + ", waiting for the Writer"
        if req.get("result"):
            return f"{phrase}. {req['result']}"
        return f"{phrase}, to be carried out within {APPLY_EVERY}"
    if status == "applying":
        return "being carried out now"
    if status == "applied":
        return f"done: {req.get('result') or 'no result recorded'}"
    return f"failed: {req.get('result') or 'no reason recorded'}"


def _public(req: dict[str, Any]) -> dict[str, Any]:
    out = {k: req.get(k) for k in ("id", "kind", "portal", "call_id", "summary", "reason", "status", "requested_by",
                                    "requested_at", "decided_by", "decided_at", "decision_note", "applied_at", "result")}
    out["payload"] = _decode(req.get("payload"))
    out["preview"] = _decode(req.get("preview"))
    return out


def _record(kind: str, summary: str, requested_by: str, preview: dict[str, Any], *, portal: str | None = None,
            call_id: str | None = None, reason: str = "", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Record the request unless an open one already asks for exactly this."""
    existing = find_open_request(kind, portal, call_id, payload)
    if existing:
        return {"request_id": existing["id"], "status": existing["status"], "duplicate": True, "kind": kind,
                "summary": existing["summary"], "preview": preview,
                "text": f"Request #{existing['id']} already asks for this ({existing['summary']}); it is "
                        f"{_status_phrase(existing)}."}
    request_id = create_request(kind, summary, requested_by or "assistant", portal=portal, call_id=call_id,
                                reason=_clean(reason) or None, payload=payload, preview=preview)
    link = dashboard_link()
    where = f"on the dashboard: {link}" if link else "on the dashboard's Requests page"
    return {"request_id": request_id, "status": "proposed", "duplicate": False, "kind": kind, "summary": summary,
            "preview": preview,
            "text": f"Request #{request_id} is waiting for approval: {summary}. Approve or reject it {where}.\n"
                    f"{preview['text']}"}


# ---------------------------------------------------------------------- the propose tools

def propose_keyword_change(portal: str, add_broad: list[str] | None = None, remove_broad: list[str] | None = None,
                           add_tight: list[str] | None = None, remove_tight: list[str] | None = None,
                           add_block: list[str] | None = None, remove_block: list[str] | None = None,
                           reason: str = "", requested_by: str = "assistant") -> dict[str, Any]:
    """Ask for a keyword change, with a preview of the stored calls it would newly keep or drop."""
    p = resolve_portal(portal)
    preview = preview_keyword_change(p.slug, add_broad=add_broad, remove_broad=remove_broad, add_tight=add_tight,
                                     remove_tight=remove_tight, add_block=add_block, remove_block=remove_block)
    changes = preview["changes"]
    shown = {
        "text": preview["text"] + "\nApproving edits the portal's keywords file, commits it, then filters every "
                                  "stored call again and reviews the newly kept ones.",
        "warnings": preview["warnings"],
        "stored_calls": preview["stored_calls"],
        "newly_kept": [{"id": c["id"], "title": c["title"]} for c in preview["newly_kept"]],
        "newly_dropped": [{"id": c["id"], "title": c["title"]} for c in preview["newly_dropped"]],
    }
    return _record("keyword_change", f"{p.name} keywords: {describe_changes(changes)}", requested_by, shown,
                   portal=p.slug, reason=reason, payload={"changes": changes})


def propose_rereview(call_id: str, context: str, reason: str = "", requested_by: str = "assistant") -> dict[str, Any]:
    """Ask for one call's AI review to run again with the team's context."""
    row = _get(call_id)
    title = row.get("title") or row["id"]
    context = _clean(context)
    if not context:
        raise ToolError("Say what the reviewer missed: that context is what can change its answer.")
    if row.get("filter_result") == "rejected":
        raise ToolError(f"The keyword filter rejected '{title}', so the AI never reviewed it. "
                        "Propose a keyword change instead.")
    if row.get("filter_result") != "kept":
        raise ToolError(f"'{title}' has not been filtered yet; the next scan filters and reviews it.")
    verdict = row.get("ai_verdict")
    now = f"The AI review said {verdict}: {_sentence(row.get('ai_reasoning') or '')}" if verdict else \
        "The AI has not reviewed it yet."
    text = (f"{now}\nThe team's context: {_sentence(context)}\nApproving asks the reviewer again with that context; "
            "its answer replaces the current one.")
    return _record("rereview", f"Re-review '{title}' with the team's context", requested_by,
                   {"text": text, "verdict": verdict, "reasoning": row.get("ai_reasoning")},
                   portal=_portal_slug(row.get("portal")), call_id=row["id"], reason=reason,
                   payload={"context": context})


def _minutes(run: dict[str, Any]) -> int | None:
    try:
        started = datetime.fromisoformat(run["started_at"].replace("Z", "+00:00"))
        finished = datetime.fromisoformat(run["finished_at"].replace("Z", "+00:00"))
    except (AttributeError, KeyError, TypeError, ValueError):
        return None
    return max(1, round((finished - started).total_seconds() / 60))


def propose_scan(portal: str, reason: str = "", requested_by: str = "assistant") -> dict[str, Any]:
    """Ask for a scan of one portal now instead of waiting for the weekly run."""
    p = resolve_portal(portal)
    runs = recent_runs(component=p.slug, limit=20)
    completed = next((r for r in runs if r["status"] == "completed"), None)
    parts = []
    if completed:
        took = _minutes(completed)
        parts.append(f"The last scan completed at {_when(completed.get('finished_at') or completed['started_at'])}"
                     + (f" and took {_plural(took, 'minute')}." if took else "."))
    else:
        parts.append(f"{p.name} has no completed scan yet.")
    if runs and runs[0]["status"] == "running":
        parts.append("A run is in progress now; an approved scan waits for it to finish.")
    parts.append(f"Approving runs one scan of {p.name} within {APPLY_EVERY}: it fetches the calls, filters and "
                 "reviews new ones, and posts them to Slack.")
    return _record("scan", f"Scan {p.name} now", requested_by, {"text": " ".join(parts)},
                   portal=p.slug, reason=reason, payload={})


def propose_draft(call_id: str, notes: str = "", reason: str = "", requested_by: str = "assistant") -> dict[str, Any]:
    """Ask for a response draft to be started for one call, from its brief."""
    brief = brief_call(call_id)
    title = brief["title"]
    if brief["closed"]:
        raise ToolError(f"The portal shows '{title}' as closed, so there is nothing to draft.")
    if brief["days_left"] is not None and brief["days_left"] < 0:
        raise ToolError(f"The deadline for '{title}' passed {_plural(-brief['days_left'], 'day')} ago.")
    notes = _clean(notes)
    text = brief["text"] + (f"\nNotes for the draft: {_sentence(notes)}" if notes else "") + \
        "\nApproving hands this brief to the Writer to start a response draft. The Writer is not built yet, " \
        "so an approved draft waits for it."
    return _record("draft", f"Start a response draft for '{title}'", requested_by,
                   {"text": text, "deadline": brief["deadline"], "days_left": brief["days_left"]},
                   portal=_portal_slug(brief.get("portal")), call_id=brief["id"], reason=reason,
                   payload={"notes": notes})


def _short(text: str, limit: int = TITLE_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0].rstrip(",;:") + "..."


def propose_fault_report(portal: str, description: str, requested_by: str = "assistant") -> dict[str, Any]:
    """Ask for a scraper fault to be filed as a GitHub issue, with the portal's recent runs as evidence."""
    p = resolve_portal(portal)
    description = _clean(description)
    if not description:
        raise ToolError("Describe what went wrong; the report starts with it.")
    health = scraper_health(p.slug)["portals"][0]
    lines = [_sentence(description), "", f"Scraper health: {health['text']}"]
    runs = recent_runs(component=p.slug, limit=5)
    if runs:
        lines += ["", "Recent runs:"]
        for run in runs:
            line = f"- #{run['id']} {run['status']}, started {_when(run['started_at'])}"
            if run.get("error"):
                line += f": {run['error']}"
            if run.get("log_path"):
                line += f" (log: {run['log_path']})"
            lines.append(line)
    lines += ["", f"Reported by {requested_by or 'assistant'} through the portal assistant."]
    body = "\n".join(lines)
    title = f"Scraper fault: {p.name}: {_short(_sentence(description))}"
    return _record("fault_report", f"Report a scraper fault in {p.name}", requested_by, {"text": body},
                   portal=p.slug, reason=description, payload={"title": title, "body": body})


# ------------------------------------------------------------------------ reading the queue

def list_change_requests(status: str | None = None, limit: int = 20) -> dict[str, Any]:
    """Change requests, newest first, and where each one stands."""
    if status is not None and status not in STATUSES:
        raise ToolError(f"'{status}' is not a request status. Use one of: {', '.join(STATUSES)}.")
    found = list_requests(status, limit=limit)
    if not found:
        return {"requests": [], "text": "No change requests" + (f" with status {status}" if status else "") + "."}
    return {"requests": [_public(r) for r in found],
            "text": "\n".join(f"#{r['id']} {r['summary']}: {_status_phrase(r)}" for r in found)}


def get_change_request(request_id: int) -> dict[str, Any]:
    """One change request in full: what it asks, its preview, the decision and the result."""
    try:
        req = get_request(int(request_id))
    except (TypeError, ValueError):
        req = None
    if req is None:
        raise ToolError(f"No change request #{request_id}.")
    return {"request": _public(req), "text": f"#{req['id']} {req['summary']}: {_status_phrase(req)}"}


# --------------------------------------------------------------------------- the registry

REASON_ARG = {"type": "string", "description": "Why the person asked for this, in their words."}

REQUEST_TOOLS = [
    Tool("propose_keyword_change", "Ask for a change to a portal's keywords. Records a request with a preview of the "
         "stored calls it would newly keep or drop; nothing changes until a person approves it on the dashboard.",
         "propose", _schema({"portal": PORTAL_ARG, "add_broad": WORDS, "remove_broad": WORDS, "add_tight": WORDS,
                             "remove_tight": WORDS, "add_block": WORDS, "remove_block": WORDS, "reason": REASON_ARG},
                            ["portal"]), propose_keyword_change),
    Tool("propose_rereview", "Ask for one call's AI review to run again with context from the team, for example "
         "when the AI said no to a call the team thinks fits. Needs a person's approval.", "propose",
         _schema({"call_id": CALL_ARG, "context": {"type": "string", "description": "What the reviewer missed."},
                  "reason": REASON_ARG}, ["call_id", "context"]), propose_rereview),
    Tool("propose_scan", "Ask for a scan of one portal now instead of waiting for the weekly run. Needs a person's "
         "approval.", "propose", _schema({"portal": PORTAL_ARG, "reason": REASON_ARG}, ["portal"]), propose_scan),
    Tool("propose_draft", "Ask for a response draft to be started for one call, from its brief. Needs a person's "
         "approval; the Writer carries it out.", "propose",
         _schema({"call_id": CALL_ARG, "notes": {"type": "string", "description": "What the draft should stress."},
                  "reason": REASON_ARG}, ["call_id"]), propose_draft),
    Tool("propose_fault_report", "Ask for a scraper fault to be filed as a GitHub issue, with the portal's recent "
         "runs as evidence. Needs a person's approval.", "propose",
         _schema({"portal": PORTAL_ARG, "description": {"type": "string", "description": "What went wrong."}},
                 ["portal", "description"]), propose_fault_report),
    Tool("list_change_requests", "Change requests, newest first, and where each stands: waiting for approval, "
         "approved, rejected, done or failed.", "read",
         _schema({"status": {"type": "string", "enum": list(STATUSES)},
                  "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 20}}),
         list_change_requests),
    Tool("get_change_request", "One change request in full: what it asks, its preview, the decision and the result.",
         "read", _schema({"request_id": {"type": "integer"}}, ["request_id"]), get_change_request),
]
