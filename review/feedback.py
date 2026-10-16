"""Recent human decisions rendered as few-shot examples for the review prompt.

    block = build_examples_block(limit=20)   # "" when nobody has decided anything yet

pursue and submitted count as PURSUE; not_relevant and dismissed as NOT RELEVANT. The
line shows the team's own note when there is one, else the AI's reasoning.
"""
from __future__ import annotations

from ledger.queries import recent_decisions

HEADER = "--- RECENT HUMAN DECISIONS (examples of what the team considers relevant) ---"
FOOTER = "---"
LABELS = {"pursue": "PURSUE", "submitted": "PURSUE", "not_relevant": "NOT RELEVANT", "dismissed": "NOT RELEVANT"}
MAX_WHY = 240


def _why(row: dict) -> str:
    notes = (row.get("human_notes") or "").strip()
    if notes:
        # keep the newest line, without its "[timestamp user]" prefix
        last = notes.splitlines()[-1]
        why = last.split("] ", 1)[1] if last.startswith("[") and "] " in last else last
    else:
        why = (row.get("ai_reasoning") or "").strip()
    return " ".join(why.split())[:MAX_WHY]


def format_examples(rows: list[dict]) -> str:
    lines = [HEADER]
    for row in rows:
        label = LABELS.get(row.get("human_status") or "")
        if not label:
            continue
        lines.append(f"- [{label}] {row.get('title') or '(untitled)'}: {_why(row)}")
    if len(lines) == 1:
        return ""
    lines.append(FOOTER)
    return "\n".join(lines) + "\n\n"


def build_examples_block(limit: int = 20) -> str:
    return format_examples(recent_decisions(limit))
