"""The portal assistant's read tools, and the registry a model is given (docs/ASSISTANT.md).

Each tool is a plain function with fixed inputs that returns a JSON-ready dict, always with a
"text" field in plain words. A model picks the tool and phrases the reply; the tool does the
exact work, so the facts never depend on the model. Read tools only read the ledger and the
portals' own files. Propose tools (assistant/requests.py) only record a change request.

Portal-specific page fields are read from calls.extra by their suffix, so any portal that
follows the convention gets them: <prefix>_objectives, _documents, _files_required, _tags,
_instructions (lists or text) and the flags _closed and _description_fallback.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from assistant.dates import days_until, parse_due
from ledger.queries import calls_where, get_call, recent_runs
from portals import registry
from portals.registry import Portal
from portals.shared import keyword_filter as kf
from portals.shared.keyword_filter import Keywords, decide, load_keywords

UTC = timezone.utc
STATUS_LABELS = {"pursue": "Pursue", "not_relevant": "Not relevant", "submitted": "Submitted", "dismissed": "Dismissed"}
POSITIVE = {"pursue", "submitted"}
NEGATIVE = {"not_relevant", "dismissed"}
VERDICTS = ("yes", "maybe", "no")
OVERDUE_DAYS = 8          # scans run weekly; more than this without a completed one is worth saying
CLOSING_WINDOW_DAYS = 14
TOP_PICKS = 5   # open, undecided calls the weekly summary ranks
RANKING = "yes before maybe, then the nearest deadline, then the newest"   # how top picks are ordered
NOTE_LINE = re.compile(r"^\[(\S+) ([^\]]+)\] ?(.*)$")
STOPWORDS = {
    "with", "from", "into", "that", "this", "their", "they", "have", "will", "your", "call", "calls",
    "open", "solution", "solutions", "system", "systems", "capability", "capabilities", "technology",
    "technologies", "program", "request", "information", "support", "based", "using", "about", "other",
}


class ToolError(Exception):
    """A request the tool cannot answer, in words fit to show the person who asked."""


# ------------------------------------------------------------------------ small helpers

def _now(now: datetime | None) -> datetime:
    return now or datetime.now(UTC)


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _when(iso: str | None) -> str:
    if not iso:
        return "an unknown time"
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso


def _extra(row: dict[str, Any]) -> dict[str, Any]:
    try:
        data = json.loads(row.get("extra") or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _extra_list(extra: dict[str, Any], suffix: str) -> list[str]:
    for key, value in extra.items():
        if key.endswith(suffix) and isinstance(value, list):
            return [str(v) for v in value if str(v).strip()]
    return []


def _extra_text(extra: dict[str, Any], suffix: str) -> str:
    for key, value in extra.items():
        if key.endswith(suffix) and isinstance(value, str):
            return value.strip()
    return ""


def _flag(extra: dict[str, Any], suffix: str) -> bool:
    return any(key.endswith(suffix) and value is True for key, value in extra.items())


def _keywords_of(row: dict[str, Any]) -> list[str]:
    try:
        data = json.loads(row.get("matched_keywords") or "[]")
    except (TypeError, ValueError):
        return []
    return [str(k) for k in data] if isinstance(data, list) else []


def _sentence(text: str) -> str:
    text = " ".join((text or "").split())
    return text if not text or text[-1] in ".!?" else text + "."


def _plural(n: int, word: str) -> str:
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def _first_sentence(text: str | None, limit: int = 160) -> str:
    """The first sentence of a review reason, cut to `limit` characters."""
    clean = " ".join((text or "").split())
    match = re.match(r"(.+?[.!?])(\s|$)", clean)
    sentence = match.group(1) if match else clean
    return sentence if len(sentence) <= limit else sentence[: limit - 1].rstrip() + "\u2026"


def _days_phrase(days: int) -> str:
    if days == 0:
        return "today"
    return _plural(days, "day")


def _badly_read(row: dict[str, Any]) -> bool:
    return not (row.get("due_date") or "").strip() or _flag(_extra(row), "_description_fallback")


def _notes(row: dict[str, Any]) -> list[dict[str, str | None]]:
    out: list[dict[str, str | None]] = []
    for line in (row.get("human_notes") or "").splitlines():
        match = NOTE_LINE.match(line)
        out.append({"at": match.group(1), "by": match.group(2), "text": match.group(3)} if match
                   else {"at": None, "by": None, "text": line})
    return out


def _call_ref(row: dict[str, Any], **more: Any) -> dict[str, Any]:
    return {"id": row["id"], "title": row.get("title") or row["id"], "portal": row.get("portal"),
            "url": row.get("url"), **more}


# ------------------------------------------------------------------------------ portals

def resolve_portal(portal: str) -> Portal:
    """A registered portal by slug or name, ignoring case."""
    wanted = (portal or "").strip().lower()
    known = registry.discover()
    for p in known:
        if wanted in (p.slug.lower(), p.name.lower()):
            return p
    names = ", ".join(p.slug for p in known) or "none"
    raise ToolError(f"No portal called '{portal}'. Known portals: {names}.")


def _portal_rows(portal: str | None) -> tuple[str, list[dict[str, Any]]]:
    if portal is None:
        return "All portals", calls_where()
    p = resolve_portal(portal)
    return p.name, calls_where(portal=p.name)


def _keywords_for(p: Portal) -> Keywords:
    if not p.keywords or not p.keywords.exists():
        raise ToolError(f"{p.name} has no keywords file.")
    return load_keywords(p.keywords)


def portal_profile(portal: str) -> dict[str, Any]:
    """What we know about one portal: how it works, its settings, its calls and its last scan."""
    p = resolve_portal(portal)
    rows = calls_where(portal=p.name)
    kw = _keywords_for(p) if p.keywords else None
    by_verdict = {v: sum(1 for r in rows if r.get("ai_verdict") == v) for v in VERDICTS}
    by_verdict["not reviewed"] = sum(1 for r in rows if r.get("filter_result") == "kept" and not r.get("ai_verdict"))
    decided = Counter(r["human_status"] for r in rows if r.get("human_status"))
    runs = recent_runs(component=p.slug, limit=1)
    last_run = runs[0] if runs else None
    calls = {
        "total": len(rows),
        "open": sum(1 for r in rows if not _flag(_extra(r), "_closed")),
        "kept": sum(1 for r in rows if r.get("filter_result") == "kept"),
        "rejected": sum(1 for r in rows if r.get("filter_result") == "rejected"),
        "by_verdict": by_verdict,
        "decided": dict(decided),
    }
    notes = p.notes.read_text(encoding="utf-8") if p.notes and p.notes.exists() else ""
    lines = [
        f"{p.name}: {calls['total']} calls in the ledger, {calls['open']} open. "
        f"{calls['kept']} passed the keyword filter; the AI rated {by_verdict['yes']} yes, "
        f"{by_verdict['maybe']} maybe and {by_verdict['no']} no.",
    ]
    if decided:
        lines.append("Team decisions: " + ", ".join(f"{STATUS_LABELS.get(s, s)} {n}" for s, n in sorted(decided.items())) + ".")
    if last_run:
        lines.append(f"Last scan: {last_run['status']}, started {_when(last_run['started_at'])}.")
    if p.how_to_submit:
        lines.append(f"How to submit: {p.how_to_submit}")
    return {
        "slug": p.slug,
        "name": p.name,
        "how_to_submit": p.how_to_submit,
        "notes": notes,
        "keywords": {"broad": kw.broad, "tight": kw.tight, "blocklist": [b.pattern for b in kw.blocklist]} if kw else None,
        "calls": calls,
        "last_run": {k: last_run[k] for k in ("id", "status", "started_at", "finished_at", "stage_counts", "error")} if last_run else None,
        "text": " ".join(lines),
    }


# ---------------------------------------------------------------------- explain a verdict

def _get(call_id: str) -> dict[str, Any]:
    row = get_call(call_id)
    if row is None:
        raise ToolError(f"No call with id '{call_id}'.")
    return row


def explain_call(call_id: str) -> dict[str, Any]:
    """Why a call was kept or rejected, what the AI said, and what the team decided."""
    row = _get(call_id)
    portal = row.get("portal") or "the portal"
    keywords = _keywords_of(row)
    result, reason, tier = row.get("filter_result"), row.get("filter_reason"), row.get("match_tier")
    verdict, reasoning = row.get("ai_verdict"), row.get("ai_reasoning")
    parts: list[str] = []
    if result == "pending":
        parts.append("It has not been filtered yet; the next run will filter it.")
    elif result == "rejected":
        if reason and reason.startswith("blocklist: "):
            parts.append(f"Rejected by the keyword filter: it matches the blocklist pattern {reason[len('blocklist: '):]}, "
                         "so it never reached the AI review.")
        elif reason == "no keyword match":
            parts.append(f"Rejected by the keyword filter: none of {portal}'s keywords appear in its title or "
                         "description, so it never reached the AI review.")
        else:
            parts.append(f"Rejected by the keyword filter: {_sentence(reason or 'no reason recorded')}")
    else:
        parts.append(f"Kept by the keyword filter as a {tier or 'keyword'} match on {', '.join(keywords) or 'its keywords'}.")
    if result != "rejected":
        if verdict:
            parts.append(f"The AI review said {verdict}: {_sentence(reasoning or '')}".rstrip(": "))
        elif result == "kept":
            parts.append("The AI review has not run on it yet.")
    status = row.get("human_status")
    if status:
        parts.append(f"The team marked it {STATUS_LABELS.get(status, status)} ({row.get('human_by') or 'someone'}, "
                     f"{_when(row.get('human_at'))}).")
    elif verdict in ("yes", "maybe"):
        parts.append("Nobody has decided on it yet; it is in the review queue.")
    notes = _notes(row)
    if notes:
        parts.append("Notes: " + "; ".join(f"{n['text']} ({n['by']})" if n["by"] else str(n["text"]) for n in notes) + ".")
    if _flag(_extra(row), "_closed"):
        parts.append("The portal shows this call as closed.")
    return {
        **_call_ref(row),
        "filter": {"result": result, "reason": reason, "tier": tier, "keywords": keywords},
        "review": {"verdict": verdict, "reasoning": reasoning, "reviewed_at": row.get("reviewed_at")},
        "decision": {"status": status, "by": row.get("human_by"), "at": row.get("human_at"), "notes": notes},
        "text": " ".join(parts),
    }


# ---------------------------------------------------------------------------- brief a call

def brief_call(call_id: str, now: datetime | None = None) -> dict[str, Any]:
    """Deadline, how to submit, required files and what they want, from the stored call."""
    row = _get(call_id)
    extra = _extra(row)
    due = parse_due(row.get("due_date"))
    left = days_until(due, _now(now)) if due else None
    closed = _flag(extra, "_closed")
    instructions = _extra_text(extra, "_instructions")
    how = instructions
    if not how:
        try:
            how = resolve_portal(row.get("portal") or "").how_to_submit
        except ToolError:
            how = ""
    brief = {
        **_call_ref(row),
        "deadline": row.get("due_date"),
        "deadline_utc": _iso(due) if due else None,
        "days_left": left,
        "closed": closed,
        "opened": row.get("posted_date"),
        "type": row.get("type"),
        "objectives": _extra_list(extra, "_objectives"),
        "how_to_submit": how,
        "files_required": _extra_list(extra, "_files_required"),
        "documents": _extra_list(extra, "_documents"),
        "tags": _extra_list(extra, "_tags"),
        "summary": " ".join((row.get("description") or "").split())[:600],
    }
    lines = [f"{brief['title']} ({row.get('portal')})"]
    if row.get("due_date"):
        timing = ("" if left is None else f", {_days_phrase(left)} left" if left >= 0 else f", passed {_plural(-left, 'day')} ago")
        lines.append(f"Deadline: {row['due_date']}{timing}.")
    if closed:
        lines.append("The portal shows this call as closed.")
    if brief["opened"]:
        lines.append(f"Opened: {brief['opened']}.")
    if brief["objectives"]:
        lines.append(f"Objectives: {', '.join(brief['objectives'])}.")
    if how:
        lines.append(f"How to submit: {_sentence(how)}")
    if brief["files_required"]:
        lines.append(f"Files required: {'; '.join(brief['files_required'])}.")
    if brief["documents"]:
        lines.append(f"Documents on the page: {'; '.join(brief['documents'])}.")
    if brief["summary"]:
        lines.append(f"What they want: {brief['summary']}")
    if row.get("url"):
        lines.append(f"Link: {row['url']}")
    brief["text"] = "\n".join(lines)
    return brief


# ---------------------------------------------------------------------- deadline reminders

def upcoming_deadlines(days: int = 14, portal: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """Calls marked Pursue, not yet Submitted, whose deadline falls within `days`."""
    moment = _now(now)
    _, rows = _portal_rows(portal)
    found = []
    for row in rows:
        if row.get("human_status") != "pursue":
            continue
        due = parse_due(row.get("due_date"))
        if due is None or not (moment <= due <= moment + timedelta(days=days)):
            continue
        found.append((due, _call_ref(row, deadline=row.get("due_date"), deadline_utc=_iso(due), days_left=days_until(due, moment))))
    calls = [item for _, item in sorted(found, key=lambda pair: pair[0])]
    if calls:
        lines = [f"Due in the next {days} days, marked Pursue and not yet submitted:"]
        lines += [f"- {_days_phrase(c['days_left'])}: {c['title']}, due {c['deadline']} ({c['portal']}) {c['url'] or ''}".rstrip()
                  for c in calls]
        text = "\n".join(lines)
    else:
        text = f"Nothing marked Pursue is due in the next {days} days."
    return {"days": days, "calls": calls, "text": text}


# ------------------------------------------------------------------------ watch the scraper

def fetch_quality(run_id: int) -> dict[str, Any]:
    """How many of a run's calls were read badly: no deadline found, or no description found."""
    rows = [r for r in calls_where() if r.get("last_run_id") == run_id]
    bad = [r for r in rows if _badly_read(r)]
    return {"run_id": run_id, "total": len(rows), "count": len(bad),
            "examples": [r.get("title") or r["id"] for r in bad[:5]]}


def _health_of(p: Portal, moment: datetime) -> dict[str, Any]:
    runs = recent_runs(component=p.slug, limit=20)
    if not runs:
        return {"slug": p.slug, "name": p.name, "latest": None, "consecutive_failures": 0,
                "badly_read": None, "text": f"{p.name} has never run."}
    latest = runs[0]
    failures = 0
    for run in runs:
        if run["status"] not in ("error", "skipped_timeout"):
            break
        failures += 1
    completed = next((r for r in runs if r["status"] == "completed"), None)
    parts: list[str] = []
    if latest["status"] in ("error", "skipped_timeout"):
        what = "timed out" if latest["status"] == "skipped_timeout" else "failed"
        parts.append(f"{p.name}: the last run {what} at {_when(latest['started_at'])}: {_sentence(latest.get('error') or 'no error recorded')}")
        if failures > 1:
            parts.append(f"It has failed {failures} runs in a row.")
    elif latest["status"] == "running":
        parts.append(f"{p.name}: a run started at {_when(latest['started_at'])} and has not finished.")
    else:
        parts.append(f"{p.name}: the last scan completed at {_when(latest.get('finished_at') or latest['started_at'])}.")
    quality = None
    if completed:
        started = datetime.fromisoformat(completed["started_at"].replace("Z", "+00:00"))
        age = int((moment - started).total_seconds() // 86400)
        if age > OVERDUE_DAYS:
            parts.append(f"There has been no completed scan for {age} days.")
        quality = fetch_quality(completed["id"])
        if quality["total"] and quality["count"]:
            parts.append(f"In that scan {quality['count']} of {quality['total']} pages read badly, "
                         f"for example: {', '.join(quality['examples'])}.")
        elif quality["total"]:
            parts.append(f"All {quality['total']} pages in that scan read cleanly.")
    else:
        parts.append("No scan has completed yet.")
    return {"slug": p.slug, "name": p.name,
            "latest": {k: latest[k] for k in ("id", "status", "started_at", "finished_at", "error")},
            "consecutive_failures": failures, "badly_read": quality, "text": " ".join(parts)}


def scraper_health(portal: str | None = None, now: datetime | None = None) -> dict[str, Any]:
    """The state of each portal's scraping: last run, failures in a row, pages read badly."""
    moment = _now(now)
    portals = [resolve_portal(portal)] if portal else registry.discover()
    entries = [_health_of(p, moment) for p in portals]
    return {"portals": entries, "text": "\n".join(e["text"] for e in entries)}


# --------------------------------------------------------------------------- weekly summary

def _bucket(row: dict[str, Any]) -> str:
    if row.get("filter_result") == "rejected":
        return "rejected by filter"
    return row.get("ai_verdict") or "not reviewed yet"


def _waiting(rows: list[dict[str, Any]], moment: datetime) -> list[tuple[dict[str, Any], datetime | None]]:
    """Open, undecided calls the review kept and rated yes or maybe, best first, with their deadlines."""
    waiting = []
    for row in rows:
        if row.get("human_status") or row.get("filter_result") != "kept" or row.get("ai_verdict") not in ("yes", "maybe"):
            continue
        due = parse_due(row.get("due_date"))
        if _flag(_extra(row), "_closed") or (due is not None and due < moment):
            continue
        waiting.append((row, due))
    # RANKING, in two stable sorts. The fit score will replace this order (PRO-487).
    waiting.sort(key=lambda pair: pair[0].get("first_seen_at") or "", reverse=True)
    waiting.sort(key=lambda pair: (pair[0]["ai_verdict"] != "yes", pair[1] is None, pair[1] or moment))
    return waiting


def _pick(row: dict[str, Any], due: datetime | None, moment: datetime) -> dict[str, Any]:
    return _call_ref(row, verdict=row["ai_verdict"], deadline=row.get("due_date"),
                     days_left=days_until(due, moment) if due else None, reason=_first_sentence(row.get("ai_reasoning")))


def top_calls(limit: int = 10, now: datetime | None = None) -> list[dict[str, Any]]:
    """The best open, undecided calls across every portal, in the weekly summary's order (RANKING)."""
    moment = _now(now)
    _, rows = _portal_rows(None)
    return [_pick(r, d, moment) for r, d in _waiting(rows, moment)[:limit]]


def weekly_summary(portal: str | None = None, days: int = 7, now: datetime | None = None) -> dict[str, Any]:
    """What is new, what is closing soon, and what the team decided, over the last `days`."""
    moment = _now(now)
    cutoff = _iso(moment - timedelta(days=days))
    name, rows = _portal_rows(portal)
    new = [r for r in rows if (r.get("first_seen_at") or "") >= cutoff]
    order = ["yes", "maybe", "no", "not reviewed yet", "rejected by filter"]
    counts = Counter(_bucket(r) for r in new)
    by_verdict = {k: counts[k] for k in order if counts[k]}
    closing = []
    for row in rows:
        due = parse_due(row.get("due_date"))
        if due is None or not (moment <= due <= moment + timedelta(days=CLOSING_WINDOW_DAYS)):
            continue
        undecided_fit = not row.get("human_status") and row.get("ai_verdict") in ("yes", "maybe")
        if undecided_fit or row.get("human_status") == "pursue":
            closing.append((due, _call_ref(row, deadline=row.get("due_date"), days_left=days_until(due, moment),
                                           status=row.get("human_status"))))
    closing_soon = [item for _, item in sorted(closing, key=lambda pair: pair[0])]
    waiting = _waiting(rows, moment)
    top_picks = [_pick(r, d, moment) for r, d in waiting[:TOP_PICKS]]
    decided = sorted((r for r in rows if r.get("human_status") and (r.get("human_at") or "") >= cutoff),
                     key=lambda r: r.get("human_at") or "", reverse=True)
    decided_refs = [_call_ref(r, status=r["human_status"], by=r.get("human_by"), at=r.get("human_at")) for r in decided]

    lines = [f"*{name}, last {days} days*"]
    if new:
        lines.append(f"{_plural(len(new), 'new call')}: " + ", ".join(f"{n} {k}" for k, n in by_verdict.items()) + ".")
        for verdict in ("yes", "maybe"):
            titles = [r.get("title") or r["id"] for r in new if r.get("ai_verdict") == verdict and r.get("filter_result") != "rejected"]
            if titles:
                lines.append(f"{verdict.capitalize()}: " + "; ".join(titles[:10]) + ("; and more" if len(titles) > 10 else ""))
    else:
        lines.append("No new calls.")
    if closing_soon:
        lines.append(f"Closing within {CLOSING_WINDOW_DAYS} days:")
        lines += [f"- {c['title']}, due {c['deadline']} ({_days_phrase(c['days_left'])})"
                  + (" marked Pursue" if c["status"] == "pursue" else "") for c in closing_soon]
    if decided_refs:
        lines.append("Decided:")
        lines += [f"- {STATUS_LABELS.get(d['status'], d['status'])}: {d['title']} ({d['by']})" for d in decided_refs]
    return {"portal": name, "days": days,
            "new": {"total": len(new), "by_verdict": by_verdict, "calls": [_call_ref(r, verdict=r.get("ai_verdict")) for r in new]},
            "closing_soon": closing_soon, "decided": decided_refs, "waiting": len(waiting), "top_picks": top_picks,
            "text": "\n".join(lines)}


# ------------------------------------------------------------- settings change, previewed

CHANGE_KEYS = kf.CHANGE_KEYS


def normalize_changes(**lists: Any) -> dict[str, list[str]]:
    """The six change lists, trimmed and de-duplicated; keywords lower-cased like the filter."""
    out = {key: kf.change_values(lists, key) for key in CHANGE_KEYS}
    if not any(out.values()):
        raise ToolError("Nothing to change: name at least one keyword or pattern to add or remove.")
    return out


def changed_keywords(p: Portal, changes: dict[str, list[str]]) -> Keywords:
    """The portal's keywords with the changes applied. Raises ToolError on anything invalid."""
    try:
        return kf.apply_changes(_keywords_for(p), changes)
    except ValueError as exc:
        raise ToolError(f"{p.name}: {exc}") from exc


def preview_keyword_change(portal: str, add_broad: list[str] | None = None, remove_broad: list[str] | None = None,
                           add_tight: list[str] | None = None, remove_tight: list[str] | None = None,
                           add_block: list[str] | None = None, remove_block: list[str] | None = None) -> dict[str, Any]:
    """Which of the portal's stored calls a keyword change would newly keep or drop. Changes nothing."""
    p = resolve_portal(portal)
    changes = normalize_changes(add_broad=add_broad, remove_broad=remove_broad, add_tight=add_tight,
                                remove_tight=remove_tight, add_block=add_block, remove_block=remove_block)
    before_kw, after_kw = _keywords_for(p), changed_keywords(p, changes)
    newly_kept, newly_dropped, warnings = [], [], []
    rows = calls_where(portal=p.name)
    for row in rows:
        before, after = decide(row, before_kw), decide(row, after_kw)
        if before.result == after.result:
            continue
        ref = _call_ref(row, ai_verdict=row.get("ai_verdict"), human_status=row.get("human_status"))
        if after.result == "kept":
            newly_kept.append({**ref, "keywords": after.keywords})
        else:
            newly_dropped.append({**ref, "reason": after.reason})
            status = row.get("human_status")
            if status in POSITIVE:
                warnings.append(f"It would drop {ref['title']}, which the team marked {STATUS_LABELS[status]}.")
            elif not status and row.get("ai_verdict") == "yes":
                warnings.append(f"It would drop {ref['title']}, which the AI rated yes.")
    lines = [f"This change to {p.name}'s keywords would keep {_plural(len(newly_kept), 'call')} the filter rejects "
             f"today and drop {_plural(len(newly_dropped), 'call')} it keeps today, out of {len(rows)} stored."]
    if newly_kept:
        lines.append("Newly kept: " + "; ".join(c["title"] for c in newly_kept) + ".")
    if newly_dropped:
        lines.append("Newly dropped: " + "; ".join(c["title"] for c in newly_dropped) + ".")
    lines += warnings
    return {"portal": p.slug, "changes": changes, "newly_kept": newly_kept, "newly_dropped": newly_dropped,
            "warnings": warnings, "stored_calls": len(rows),
            "keywords_after": {"broad": after_kw.broad, "tight": after_kw.tight, "blocklist": [b.pattern for b in after_kw.blocklist]},
            "text": " ".join(lines)}


# ---------------------------------------------------------------------------- tuning report

def _terms(title: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]{4,}", (title or "").lower()) if w not in STOPWORDS}


def tuning_report(portal: str, min_examples: int = 3) -> dict[str, Any]:
    """Patterns in the team's decisions that suggest a keyword or company-profile change."""
    p = resolve_portal(portal)
    rows = calls_where(portal=p.name)
    decided = [r for r in rows if r.get("human_status")]
    if len(decided) < min_examples:
        return {"portal": p.slug, "decided": len(decided), "suggestions": [], "ai_disagreements": [],
                "text": f"Only {_plural(len(decided), 'decision')} so far for {p.name}; a pattern needs at least "
                        f"{min_examples} examples."}
    kw = _keywords_for(p)
    positive = [r for r in decided if r["human_status"] in POSITIVE]
    negative = [r for r in decided if r["human_status"] in NEGATIVE]
    suggestions: list[dict[str, Any]] = []

    hits: dict[str, dict[str, list[str]]] = {}
    for row, side in [(r, "pos") for r in positive] + [(r, "neg") for r in negative]:
        for word in _keywords_of(row):
            hits.setdefault(word, {"pos": [], "neg": []})[side].append(row.get("title") or row["id"])
    for word, seen in sorted(hits.items()):
        if word in kw.broad and len(seen["neg"]) >= min_examples and not seen["pos"]:
            suggestions.append({"kind": "remove_broad", "value": word, "count": len(seen["neg"]), "evidence": seen["neg"][:5],
                                "why": f"'{word}' matched {_plural(len(seen['neg']), 'decided call')}, all marked not relevant."})

    neg_terms = Counter(t for r in negative for t in _terms(r.get("title") or ""))
    pos_terms = {t for r in positive for t in _terms(r.get("title") or "")}
    for term, count in sorted(neg_terms.items(), key=lambda pair: (-pair[1], pair[0])):
        if count < min_examples or term in pos_terms or term in kw.broad or term in kw.tight:
            continue
        if any(b.search(term) for b in kw.blocklist):
            continue
        evidence = [r.get("title") or r["id"] for r in negative if term in _terms(r.get("title") or "")]
        suggestions.append({"kind": "add_block", "value": rf"\b{term}\b", "count": count, "evidence": evidence[:5],
                            "why": f"'{term}' is in {_plural(count, 'title')} the team marked not relevant and none it pursued."})

    disagreements = [_call_ref(r, ai_verdict=r.get("ai_verdict"), human_status=r["human_status"],
                               notes=[n["text"] for n in _notes(r)])
                     for r in decided
                     if (r["human_status"] in NEGATIVE and r.get("ai_verdict") in ("yes", "maybe"))
                     or (r["human_status"] in POSITIVE and r.get("ai_verdict") == "no")]

    lines = [f"{p.name}: {_plural(len(decided), 'decision')}, {len(positive)} to pursue or submitted and "
             f"{len(negative)} not relevant or dismissed."]
    for s in suggestions:
        action = "Remove broad keyword" if s["kind"] == "remove_broad" else "Add blocklist pattern"
        lines.append(f"- {action} {s['value']}: {s['why']}")
    if disagreements:
        lines.append("The AI and the team disagreed on these; what they have in common may belong in the "
                     "reviewer's company profile:")
        lines += [f"- {d['title']}: AI said {d['ai_verdict']}, team said {STATUS_LABELS[d['human_status']]}"
                  + (f" ({'; '.join(d['notes'])})" if d["notes"] else "") for d in disagreements]
    if not suggestions and not disagreements:
        lines.append("No clear patterns yet.")
    return {"portal": p.slug, "decided": len(decided), "suggestions": suggestions,
            "ai_disagreements": disagreements, "text": "\n".join(lines)}


# --------------------------------------------------------------------------- the registry

@dataclass(frozen=True)
class Tool:
    """One action, described the way model APIs expect a function tool."""

    name: str
    description: str
    permission: str            # "read" or "propose"
    parameters: dict[str, Any]
    run: Callable[..., dict[str, Any]] = field(compare=False)


def _schema(properties: dict[str, Any], required: list[str] | None = None) -> dict[str, Any]:
    return {"type": "object", "properties": properties, "required": required or [], "additionalProperties": False}


PORTAL_ARG = {"type": "string", "description": "Portal slug or name, for example vulcan_sof or Vulcan SOF."}
CALL_ARG = {"type": "string", "description": "The call's id, for example vulcan-1418c132-ffef-4e9a-a83b-c7adf5798c70."}
WORDS = {"type": "array", "items": {"type": "string"}}

READ_TOOLS = [
    Tool("portal_profile", "What we know about one portal: how it works, how to submit, its keyword settings, "
         "how many calls it has and how its last scan went.", "read",
         _schema({"portal": PORTAL_ARG}, ["portal"]), portal_profile),
    Tool("explain_call", "Why a call was kept or rejected by the keyword filter, what the AI review said, and what "
         "the team decided.", "read", _schema({"call_id": CALL_ARG}, ["call_id"]), explain_call),
    Tool("brief_call", "A short brief of one call: deadline and days left, how to submit, required files, "
         "documents and what they want.", "read", _schema({"call_id": CALL_ARG}, ["call_id"]), brief_call),
    Tool("upcoming_deadlines", "Calls marked Pursue and not yet submitted whose deadline is within the given "
         "number of days, nearest first.", "read",
         _schema({"days": {"type": "integer", "minimum": 1, "maximum": 90, "default": 14}, "portal": PORTAL_ARG}),
         upcoming_deadlines),
    Tool("scraper_health", "How each portal's scraping is going: the last run, failures in a row, and pages read "
         "badly.", "read", _schema({"portal": PORTAL_ARG}), scraper_health),
    Tool("weekly_summary", "New calls by verdict, calls closing within 14 days, and the team's decisions over the "
         "last few days.", "read",
         _schema({"portal": PORTAL_ARG, "days": {"type": "integer", "minimum": 1, "maximum": 31, "default": 7}}),
         weekly_summary),
    Tool("preview_keyword_change", "Which stored calls a change to a portal's keywords would newly keep or drop. "
         "Changes nothing; propose_keyword_change asks for approval.", "read",
         _schema({"portal": PORTAL_ARG, "add_broad": WORDS, "remove_broad": WORDS, "add_tight": WORDS,
                  "remove_tight": WORDS, "add_block": WORDS, "remove_block": WORDS}, ["portal"]),
         preview_keyword_change),
    Tool("tuning_report", "Patterns in the team's decisions that suggest a keyword change or a change to the "
         "reviewer's company profile.", "read",
         _schema({"portal": PORTAL_ARG, "min_examples": {"type": "integer", "minimum": 2, "default": 3}}, ["portal"]),
         tuning_report),
]

def all_tools() -> list[Tool]:
    """Every tool a model may be given: these read tools, then the request tools in assistant/requests.py."""
    from assistant.requests import REQUEST_TOOLS   # imported here: requests.py builds on this module

    return [*READ_TOOLS, *REQUEST_TOOLS]


def tool(name: str) -> Tool:
    for t in all_tools():
        if t.name == name:
            return t
    raise ToolError(f"No tool called '{name}'.")
