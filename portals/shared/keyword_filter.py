"""Keyword relevance filter shared by every portal, applied before any LLM review.

    kept, rejected = filter_calls(rows, keywords_path)   # each portal passes its own keywords.yaml

Each row needs id, title and description. Decisions are written to the ledger with
set_filter(). Order of rules: blocklist regex rejects; no broad keyword rejects; otherwise
keep, "tight" if a tight keyword also hits, else "broad". Matching is substring on the
lowercased title + description, on purpose: it is predictable and editable from YAML.
Known weakness: "ai" matches "maintain"; the tight tier and the LLM phase handle that.

Approved keyword changes (docs/ASSISTANT.md) are written with edit_keywords_text(), which
changes only the lines it adds or removes, so the file's comments and layout survive.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ledger.queries import set_filter

REASON_NO_KEYWORD = "no keyword match"

# A keyword change: lists of values to add or remove, keyed by these names.
CHANGE_KEYS = ("add_broad", "remove_broad", "add_tight", "remove_tight", "add_block", "remove_block")
SECTIONS = {"broad": "broad_keywords", "tight": "tight_keywords", "block": "blocklist_patterns"}
NOUNS = {"broad": "broad keyword", "tight": "tight keyword", "block": "blocklist pattern"}
LIST_NAMES = {"broad": "broad keywords", "tight": "tight keywords", "block": "blocklist"}
ITEM_LINE = re.compile(r"^(\s*)-\s+(.*?)\s*$")


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


def load_keywords_text(text: str, name: str = "keywords.yaml") -> Keywords:
    data = yaml.safe_load(text) or {}
    for key in SECTIONS.values():
        if not isinstance(data.get(key), list):
            raise ValueError(f"{name}: '{key}' must be a list")
    return Keywords(
        broad=[str(k).lower() for k in data["broad_keywords"]],
        tight=[str(k).lower() for k in data["tight_keywords"]],
        blocklist=[re.compile(str(p), re.IGNORECASE) for p in data["blocklist_patterns"]],
    )


def load_keywords(path: Path) -> Keywords:
    return load_keywords_text(path.read_text(encoding="utf-8"), path.name)


# ------------------------------------------------------------------- keyword changes

def change_values(changes: Mapping[str, Iterable[str] | None], key: str) -> list[str]:
    """One change list, trimmed and de-duplicated; keywords lower-cased as the loader does."""
    values = [str(v).strip() for v in (changes.get(key) or []) if str(v).strip()]
    if not key.endswith("_block"):
        values = [v.lower() for v in values]
    return list(dict.fromkeys(values))


def describe_changes(changes: Mapping[str, Iterable[str] | None]) -> str:
    """In words, e.g. "add broad keyword 'digital twin'; remove blocklist pattern '\\bhardware\\b'"."""
    parts = []
    for key in CHANGE_KEYS:
        values = change_values(changes, key)
        if values:
            verb, kind = key.split("_", 1)
            noun = NOUNS[kind] + ("s" if len(values) > 1 else "")
            parts.append(f"{verb} {noun} " + ", ".join(f"'{v}'" for v in values))
    return "; ".join(parts)


def apply_changes(kw: Keywords, changes: Mapping[str, Iterable[str] | None]) -> Keywords:
    """The keywords with the changes applied: removals first, then additions at the end."""
    lists = {"broad": list(kw.broad), "tight": list(kw.tight), "block": [b.pattern for b in kw.blocklist]}
    for kind, current in lists.items():
        for value in change_values(changes, f"remove_{kind}"):
            if value not in current:
                raise ValueError(f"'{value}' is not in the {LIST_NAMES[kind]}.")
            current.remove(value)
        for value in change_values(changes, f"add_{kind}"):
            if value not in current:
                current.append(value)
    compiled = []
    for pattern in lists["block"]:
        try:
            compiled.append(re.compile(pattern, re.IGNORECASE))
        except re.error as exc:
            raise ValueError(f"'{pattern}' is not a valid blocklist pattern: {exc}.") from exc
    return Keywords(broad=lists["broad"], tight=lists["tight"], blocklist=compiled)


def _section(lines: list[str], key: str) -> tuple[int, int]:
    """(header line, first line after the section) for one top-level list."""
    header = re.compile(rf"^{re.escape(key)}:(.*)$")
    for i, line in enumerate(lines):
        found = header.match(line)
        if not found:
            continue
        rest = found.group(1).strip()
        if rest and not rest.startswith("#"):
            raise ValueError(f"{key} is written inline; the editor only handles one item per line.")
        end = i + 1
        while end < len(lines) and not re.match(r"^[^\s#-]", lines[end]):
            end += 1
        return i, end
    raise ValueError(f"The keywords file has no {key} section.")


def _item_value(line: str) -> str | None:
    found = ITEM_LINE.match(line)
    if not found:
        return None
    try:
        value = yaml.safe_load(found.group(2))
    except yaml.YAMLError:
        value = found.group(2)
    return "" if value is None else str(value)


def _same(kind: str, a: str | None, b: str) -> bool:
    if a is None:
        return False
    return a == b if kind == "block" else a.lower() == b.lower()


def _yaml_scalar(value: str, quote: bool) -> str:
    """Bare when YAML reads it back unchanged; otherwise single-quoted. Patterns are always quoted."""
    if not quote:
        try:
            if yaml.safe_load(f"- {value}") == [value]:
                return value
        except yaml.YAMLError:
            pass
    return "'" + value.replace("'", "''") + "'"


def edit_keywords_text(text: str, changes: Mapping[str, Iterable[str] | None], note: str | None = None) -> str:
    """The keywords file with the changes made, touching only the lines added or removed.

    A removal deletes the item's line. Additions go after the section's last item, under a
    "# <note>" comment when a note is given. Raises ValueError when a value to remove is not
    there, when a section is written inline, or when the result would not load to exactly
    the expected keywords.
    """
    expected = apply_changes(load_keywords_text(text), changes)
    lines = text.split("\n")
    for kind, key in SECTIONS.items():
        start, end = _section(lines, key)
        body = lines[start + 1:end]
        dropped: set[int] = set()
        for value in change_values(changes, f"remove_{kind}"):
            index = next((i for i, line in enumerate(body) if i not in dropped and _same(kind, _item_value(line), value)), None)
            if index is None:
                raise ValueError(f"'{value}' is not in the {LIST_NAMES[kind]}.")
            dropped.add(index)
        body = [line for i, line in enumerate(body) if i not in dropped]
        items = [i for i, line in enumerate(body) if ITEM_LINE.match(line)]
        present = [_item_value(body[i]) for i in items]
        adds = [v for v in change_values(changes, f"add_{kind}") if not any(_same(kind, p, v) for p in present)]
        if adds:
            indent = ITEM_LINE.match(body[items[0]]).group(1) if items else "  "   # type: ignore[union-attr]
            new_lines = [f"{indent}# {note}"] if note else []
            new_lines += [f"{indent}- {_yaml_scalar(v, quote=kind == 'block')}" for v in adds]
            at = items[-1] + 1 if items else 0
            body[at:at] = new_lines
        lines[start + 1:end] = body
    result = "\n".join(lines)
    got = load_keywords_text(result)
    if (got.broad, got.tight, [b.pattern for b in got.blocklist]) != (
            expected.broad, expected.tight, [b.pattern for b in expected.blocklist]):
        raise ValueError("The edit would not produce the expected keywords; change the file by hand.")
    return result


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


def filter_calls(rows: Iterable[Mapping[str, Any]], keywords_path: Path) -> tuple[list[Decision], list[Decision]]:
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
