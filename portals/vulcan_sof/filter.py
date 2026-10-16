"""Deterministic relevance filter for scraped calls, applied before any LLM review.

    kept, rejected = filter_calls(rows, keywords_path)

Each row needs id, title and description. Decisions are written to the ledger with
set_filter(). Order of rules: blocklist regex rejects; no broad keyword rejects; otherwise
keep, "tight" if a tight keyword also hits, else "broad". Matching is substring on the
lowercased title + description, on purpose: it is predictable and editable from YAML.
Known weakness: "ai" matches "maintain"; the tight tier and the LLM phase handle that.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ledger.queries import set_filter

KEYWORDS_PATH = Path(__file__).resolve().parent / "keywords.yaml"

REASON_NO_KEYWORD = "no keyword match"


@dataclass
class Keywords:
    broad: list[str]
    tight: list[str]
    blocklist: list[re.Pattern[str]] = field(default_factory=list)


@dataclass
class Decision:
    id: str
    title: str
    result: str                 # "kept" or "rejected"
    reason: str | None = None   # for rejections
    tier: str | None = None     # "tight" or "broad" for kept rows
    keywords: list[str] = field(default_factory=list)


def load_keywords(path: Path = KEYWORDS_PATH) -> Keywords:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    for key in ("broad_keywords", "tight_keywords", "blocklist_patterns"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"{path.name}: '{key}' must be a list")
    return Keywords(
        broad=[str(k).lower() for k in data["broad_keywords"]],
        tight=[str(k).lower() for k in data["tight_keywords"]],
        blocklist=[re.compile(str(p), re.IGNORECASE) for p in data["blocklist_patterns"]],
    )


def search_text(row: Mapping[str, Any]) -> str:
    return f"{row.get('title') or ''} {row.get('description') or ''}".lower()


def decide(row: Mapping[str, Any], kw: Keywords) -> Decision:
    text = search_text(row)
    title = str(row.get("title") or "")
    for pattern in kw.blocklist:
        if pattern.search(text):
            return Decision(row["id"], title, "rejected", reason=f"blocklist: {pattern.pattern}")
    broad_hits = [k for k in kw.broad if k in text]
    if not broad_hits:
        return Decision(row["id"], title, "rejected", reason=REASON_NO_KEYWORD)
    tight_hits = [k for k in kw.tight if k in text]
    hits = list(dict.fromkeys(broad_hits + tight_hits))
    return Decision(row["id"], title, "kept", tier="tight" if tight_hits else "broad", keywords=hits)


def filter_calls(rows: Iterable[Mapping[str, Any]], keywords_path: Path = KEYWORDS_PATH) -> tuple[list[Decision], list[Decision]]:
    """Decide every row, write each decision to the ledger, return (kept, rejected)."""
    kw = load_keywords(keywords_path)
    kept: list[Decision] = []
    rejected: list[Decision] = []
    for row in rows:
        d = decide(row, kw)
        if d.result == "kept":
            set_filter(d.id, "kept", reason=None, tier=d.tier, keywords=d.keywords)
            kept.append(d)
        else:
            set_filter(d.id, "rejected", reason=d.reason, tier=None, keywords=None)
            rejected.append(d)
    return kept, rejected
