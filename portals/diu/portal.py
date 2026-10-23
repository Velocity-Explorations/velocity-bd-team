"""DIU as the pipeline sees it (see portals/registry.py for the contract)."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from portals.diu.records import PORTAL as PORTAL_NAME
from portals.diu.scrape import fetch_all
from portals.shared.keyword_filter import filter_calls

SLUG = "diu"
KEYWORDS_PATH = Path(__file__).resolve().parent / "keywords.yaml"   # this portal's filter settings
NOTES_PATH = Path(__file__).resolve().parent / "NOTES.md"           # what the assistant should know
HOW_TO_SUBMIT = (
    "Respond through the solicitation's own page on diu.mil before its close time. A CSO response "
    "starts with a short solution brief; DIU invites the strongest to pitch, then to propose."
)


def fetch(page: Any, run_id: int, limit: int | None = None) -> dict[str, int]:
    """No browser: the pipeline passes page=None for this portal."""
    return fetch_all(run_id, limit=limit)


def filter_rows(rows: list[dict[str, Any]]) -> tuple[list[Any], list[Any]]:
    return filter_calls(rows, KEYWORDS_PATH)


PORTAL = {
    "slug": SLUG,
    "name": PORTAL_NAME,
    "fetch": fetch,
    "filter": filter_rows,
    "fetch_timeout": 120,
    "needs_browser": False,
    "keywords": KEYWORDS_PATH,
    "how_to_submit": HOW_TO_SUBMIT,
    "notes": NOTES_PATH,
}
