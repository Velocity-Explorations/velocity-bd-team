"""Recent human decisions rendered as few-shot examples for the review prompt.

    block = build_examples_block(limit=20)   # "" when nobody has decided anything yet

pursue and submitted count as PURSUE; not_relevant and dismissed as NOT RELEVANT. The AI's
reasoning appears only where its verdict agrees with the decision: its case for a call the team
passed on would teach the judges the opposite. On NOT RELEVANT the team's note is the reason and
stands in its place. On PURSUE a note follows it, because a note there is often a side remark.
"""
from __future__ import annotations

from ledger.queries import recent_decisions

HEADER = "--- RECENT HUMAN DECISIONS (examples of what the team considers relevant) ---"
FOOTER = "---"
LABELS = {"pursue": "PURSUE", "submitted": "PURSUE", "not_relevant": "NOT RELEVANT", "dismissed": "NOT RELEVANT"}
AGREES = {"PURSUE": ("yes", "maybe"), "NOT RELEVANT": ("no",)}   # the AI verdicts that agree with each label
MAX_WHY = 240


def _short(text: str) -> str:
    return " ".join(text.split())[:MAX_WHY]


def _newest_note(row: dict) -> str:
    """The newest line of the team's notes, without its "[timestamp user]" prefix."""
    notes = (row.get("human_notes") or "").strip()
    if not notes:
        return ""
    last = notes.splitlines()[-1]
    return _short(last.split("] ", 1)[1] if last.startswith("[") and "] " in last else last)


def _why(row: dict, label: str) -> str:
    note = _newest_note(row)
    if note and label == "NOT RELEVANT":
        return note
    reasoning = _short(row.get("ai_reasoning") or "") if row.get("ai_verdict") in AGREES[label] else ""
    if note:
        return f"{reasoning} (team note: {note})" if reasoning else f"team note: {note}"
    return reasoning


def format_examples(rows: list[dict]) -> str:
    lines = [HEADER]
    for row in rows:
        label = LABELS.get(row.get("human_status") or "")
        if not label:
            continue
        why = _why(row, label)
        lines.append(f"- [{label}] {row.get('title') or '(untitled)'}" + (f": {why}" if why else ""))
    if len(lines) == 1:
        return ""
    lines.append(FOOTER)
    return "\n".join(lines) + "\n\n"


def build_examples_block(limit: int = 20) -> str:
    return format_examples(recent_decisions(limit))
