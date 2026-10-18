"""Reads the retired Yukon pipeline's prompt text for the Writer's tests, without importing it.

AGENTS.md hard rule 5: reference/yukon/ is never imported. This module parses the
reference file's syntax tree and pulls out its string constants, so a test can prove the
port kept every word. The port swaps the em dashes for other punctuation (David's no-dash
rule); undash() applies exactly those swaps, so undash(reference) must equal the port.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path
from typing import Any

REFERENCE = Path(__file__).resolve().parent.parent / "reference" / "yukon" / "rfp_response_agent.py"
TEMPLATES = Path(__file__).resolve().parent.parent / "reference" / "yukon" / "templates"
DASHES = ("\u2013", "\u2014")

# Where a colon would read badly, the port uses this punctuation instead.
SPECIAL_SWAPS = {
    "contracts, or results \u2014 or just general assertions?": "contracts, or results, or just general assertions?",
    "past deployments \u2014 Space Force, Navy, INDOPACOM \u2014 to substantiate claims.":
        "past deployments (Space Force, Navy, INDOPACOM) to substantiate claims.",
}


def undash(text: str) -> str:
    """The reference text with its em dashes swapped the way the port swaps them."""
    for old, new in SPECIAL_SWAPS.items():
        text = text.replace(old, new)
    return text.replace(" \u2014 ", ": ")


@lru_cache(maxsize=1)
def reference_constants() -> dict[str, Any]:
    """Module-level *_PROMPT strings and REVIEW_PASSES from the reference script."""
    tree = ast.parse(REFERENCE.read_text(encoding="utf-8"))
    found: dict[str, Any] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name.endswith("_PROMPT") or name in ("REVIEW_PASSES", "TEMPLATE_MAP"):
                found[name] = ast.literal_eval(node.value)
    return found


def reference_source() -> str:
    return REFERENCE.read_text(encoding="utf-8")
